// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {
    uint256 internal constant BASE_FEE = 30 * BPS;
    uint256 internal constant FEE_FLOOR = 10 * BPS;
    uint256 internal constant FEE_CAP = 500 * BPS;
    uint256 internal constant ARB_THR = WAD / 60;
    uint256 internal constant LARGE_THR = WAD / 250;
    uint256 internal constant ARB_BUMP = 350 * BPS;
    uint256 internal constant LARGE_BUMP = 100 * BPS;
    uint256 internal constant CONSEC_BUMP = 3 * BPS;
    uint256 internal constant DECAY = 7 * BPS;
    uint256 internal constant SKEW_MAX = 450 * BPS;
    uint256 internal constant SKEW_DECAY = 5;
    uint256 internal constant FAIR_DECAY = 30;
    uint256 internal constant FAIR_BLEND = WAD / 50;
    uint256 internal constant NONE = type(uint256).max;

    function afterInitialize(uint256 reserveX, uint256 reserveY) external override returns (uint256, uint256) {
        uint256 p = wdiv(reserveY, reserveX);
        slots[0] = NONE;
        slots[1] = p;
        slots[2] = p;
        slots[3] = WAD;
        slots[6] = BASE_FEE; slots[7] = BASE_FEE;
        slots[8] = 0; slots[9] = 0; slots[10] = 0;
        slots[14] = BASE_FEE; slots[15] = BASE_FEE;
        return (BASE_FEE, BASE_FEE);
    }

    function afterSwap(TradeInfo calldata t) external override returns (uint256, uint256) {
        uint256 lastTs = slots[0];
        uint256 fairPrice = slots[1];
        uint256 preSpot = slots[2];
        uint256 invSkew = slots[3];
        uint256 bid = slots[6];
        uint256 ask = slots[7];
        uint256 tc = slots[8];
        uint256 ls = slots[9];
        uint256 cs = slots[10];

        uint256 elapsed = (lastTs == NONE || t.timestamp > lastTs) ? (lastTs == NONE ? 1 : t.timestamp - lastTs) : 0;
        if (elapsed > 0) { tc = 0; } else { tc += 1; }
        if (elapsed > 0) {
            if (invSkew > WAD) invSkew = invSkew - (invSkew - WAD) / SKEW_DECAY;
            else if (invSkew < WAD) invSkew = invSkew + (WAD - invSkew) / SKEW_DECAY;
            fairPrice = fairPrice + (preSpot > fairPrice ? (preSpot - fairPrice) / FAIR_DECAY : 0);
            fairPrice = fairPrice - (fairPrice > preSpot ? (fairPrice - preSpot) / FAIR_DECAY : 0);
        }

        uint256 tr = wdiv(t.amountY, t.reserveY);
        bool isBuy = t.isBuy;
        bool isArb = tr > ARB_THR; bool isLg = tr > LARGE_THR;
        uint256 cSide = isBuy ? 1 : 0;
        if (cSide == ls && tc > 1) cs += 1; else cs = 1;
        slots[9] = cSide; slots[10] = cs;

        if (isBuy) {
            invSkew = invSkew + wmul(invSkew, tr);
            if (invSkew > WAD * 5) invSkew = WAD * 5;
        } else {
            uint256 dec = wmul(invSkew, tr);
            invSkew = invSkew > dec ? invSkew - dec : WAD / 5;
        }
        slots[3] = invSkew;

        uint256 preReserveX = isBuy ? t.reserveX + t.amountX : t.reserveX - t.amountX;
        uint256 preReserveY = isBuy ? t.reserveY - t.amountY : t.reserveY + t.amountY;
        uint256 preTradeSpot = wdiv(preReserveY, preReserveX);
        slots[2] = preTradeSpot;

        uint256 postTradeSpot = wdiv(t.reserveY, t.reserveX);
        if (isArb) {
            uint256 observedFair;
            if (isBuy) {
                observedFair = wmul(postTradeSpot, WAD - bid);
            } else {
                observedFair = wdiv(postTradeSpot, WAD - ask);
            }
            fairPrice = fairPrice + wmul(observedFair > fairPrice ? observedFair - fairPrice : fairPrice - observedFair, FAIR_BLEND);
        }
        slots[1] = fairPrice;

        if (isArb) { if (isBuy) ask = ask + ARB_BUMP > FEE_CAP ? FEE_CAP : ask + ARB_BUMP; else bid = bid + ARB_BUMP > FEE_CAP ? FEE_CAP : bid + ARB_BUMP; }
        else if (isLg) { if (isBuy) ask = ask + LARGE_BUMP > FEE_CAP ? FEE_CAP : ask + LARGE_BUMP; else bid = bid + LARGE_BUMP > FEE_CAP ? FEE_CAP : bid + LARGE_BUMP; }
        if (cs >= 3) { uint256 bump = (cs - 2) * CONSEC_BUMP; if (cSide == 1) { bid = bid + bump > FEE_CAP ? FEE_CAP : bid + bump; } else { ask = ask + bump > FEE_CAP ? FEE_CAP : ask + bump; } }

        if (invSkew > WAD) {
            uint256 skew = wmul(SKEW_MAX, (invSkew - WAD) / invSkew);
            if (ask > skew) ask = ask - skew; else ask = FEE_FLOOR;
            bid = bid + skew > FEE_CAP ? FEE_CAP : bid + skew;
            bid = bid + skew / 2 > FEE_CAP ? FEE_CAP : bid + skew / 2;
        } else if (invSkew < WAD) {
            uint256 skew = wmul(SKEW_MAX, (WAD - invSkew) / WAD);
            if (bid > skew) bid = bid - skew; else bid = FEE_FLOOR;
            ask = ask + skew > FEE_CAP ? FEE_CAP : ask + skew;
            ask = ask + skew / 2 > FEE_CAP ? FEE_CAP : ask + skew / 2;
        }

        uint256 targetBid = BASE_FEE; uint256 targetAsk = BASE_FEE;
        if (fairPrice > 0) {
            if (postTradeSpot > fairPrice) {
                uint256 misprice = wdiv(postTradeSpot - fairPrice, fairPrice);
                uint256 adj = wmul(misprice, SKEW_MAX);
                if (adj > BASE_FEE) adj = BASE_FEE;
                targetBid = BASE_FEE + adj;
                targetAsk = BASE_FEE > adj ? BASE_FEE - adj : FEE_FLOOR;
            } else if (postTradeSpot < fairPrice) {
                uint256 misprice = wdiv(fairPrice - postTradeSpot, fairPrice);
                uint256 adj = wmul(misprice, SKEW_MAX);
                if (adj > BASE_FEE) adj = BASE_FEE;
                targetAsk = BASE_FEE + adj;
                targetBid = BASE_FEE > adj ? BASE_FEE - adj : FEE_FLOOR;
            }
        }
        if (invSkew > WAD) {
            uint256 skew = wmul(SKEW_MAX, (invSkew - WAD) / invSkew);
            if (targetAsk > skew) targetAsk = targetAsk - skew; else targetAsk = FEE_FLOOR;
            targetBid = targetBid + skew > FEE_CAP ? FEE_CAP : targetBid + skew;
            targetBid = targetBid + skew / 2 > FEE_CAP ? FEE_CAP : targetBid + skew / 2;
        } else if (invSkew < WAD) {
            uint256 skew = wmul(SKEW_MAX, (WAD - invSkew) / WAD);
            if (targetBid > skew) targetBid = targetBid - skew; else targetBid = FEE_FLOOR;
            targetAsk = targetAsk + skew > FEE_CAP ? FEE_CAP : targetAsk + skew;
            targetAsk = targetAsk + skew / 2 > FEE_CAP ? FEE_CAP : targetAsk + skew / 2;
        }
        if (isArb) { if (isBuy) targetAsk = targetAsk + ARB_BUMP > FEE_CAP ? FEE_CAP : targetAsk + ARB_BUMP; else targetBid = targetBid + ARB_BUMP > FEE_CAP ? FEE_CAP : targetBid + ARB_BUMP; }

        if (elapsed > 0) { uint256 d = elapsed * DECAY; bid = _toward(bid, targetBid, d); ask = _toward(ask, targetAsk, d); }
        bid = clamp(bid, FEE_FLOOR, FEE_CAP); ask = clamp(ask, FEE_FLOOR, FEE_CAP);
        slots[0] = t.timestamp; slots[3] = invSkew; slots[6] = bid; slots[7] = ask; slots[8] = tc; slots[14] = bid; slots[15] = ask;
        return (clampFee(bid), clampFee(ask));
    }
    function getName() external pure override returns (string memory) { return "HybridBest"; }
    function _toward(uint256 v, uint256 t, uint256 s) internal pure returns (uint256) { if (v > t) return v - t > s ? v - s : t; if (v < t) return t - v > s ? v + s : t; return v; }
}
