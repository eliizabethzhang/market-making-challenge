// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {TradeInfo} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {
    // --- Constants ---
    uint256 constant ELAPSED_CAP = 8;
    uint256 constant SIGNAL_THRESHOLD = WAD / 550;
    uint256 constant DIR_DECAY = 780000000000000000;
    uint256 constant ACT_DECAY = 620000000000000000;
    uint256 constant SIZE_DECAY = 620000000000000000;
    uint256 constant TOX_DECAY = 910000000000000000;
    uint256 constant SIGMA_DECAY = 760000000000000000;
    uint256 constant LAMBDA_DECAY = 990000000000000000;
    uint256 constant SIZE_BLEND_DECAY = 820000000000000000;
    uint256 constant TOX_BLEND_DECAY = 51000000000000000;
    uint256 constant ACT_BLEND_DECAY = 985000000000000000;
    uint256 constant PHAT_ALPHA = 265000000000000000;
    uint256 constant PHAT_ALPHA_RETAIL = 55000000000000000;
    uint256 constant DIR_IMPACT_MULT = 3;
    uint256 constant GATE_SIGMA_MULT = 9 * WAD;
    uint256 constant MIN_GATE = 30000000000000000;
    uint256 constant RET_CAP = WAD / 15;
    uint256 constant TOX_CAP = WAD / 5;
    uint256 constant TRADE_RATIO_CAP = WAD / 5;
    uint256 constant LAMBDA_CAP = 3 * WAD;
    uint256 constant BASE_FEE = 3 * BPS;
    uint256 constant SIGMA_COEF = 200000000000000000;
    uint256 constant LAMBDA_COEF = 12 * BPS;
    uint256 constant FLOW_SIZE_COEF = 4842 * BPS;
    uint256 constant TOX_LINEAR_COEF = 280 * BPS;
    uint256 constant TOX_QUAD_COEF = 13000 * BPS;
    uint256 constant ACT_COEF = 91843 * BPS;
    uint256 constant DIR_LINEAR_COEF = 20 * BPS;
    uint256 constant DIR_TOX_COEF = 100 * BPS;
    uint256 constant STALE_DIR_COEF = 6850 * BPS;
    uint256 constant STALE_ATTRACT_FRAC = 1080000000000000000;
    uint256 constant SIGMA_TOX_COEF = 500 * BPS;
    uint256 constant TRADE_TOX_BOOST = 3000 * BPS;
    uint256 constant MAX_FEE_CAP = 500 * BPS;
    uint256 constant MIN_FEE_CAP = 200 * BPS;
    uint256 constant CAP_SIGMA_SENSITIVITY = 2000000000000000000;
    uint256 constant TAIL_KNEE = 550 * BPS;
    uint256 constant TAIL_SLOPE_PROTECT = 925000000000000000;
    uint256 constant TAIL_SLOPE_ATTRACT = 875000000000000000;

    // slots: [0]=bidFee, [1]=askFee, [2]=lastTs, [3]=dirState, [4]=actEma, [5]=pHat
    // [6]=sigmaHat, [7]=lambdaHat, [8]=sizeHat, [9]=toxEma, [10]=stepTradeCount
    // [11]=lastSide, [12]=consecCount, [13]=dynamicFeeCap, [14]=prevSpot

    function afterInitialize(uint256 initialX, uint256 initialY) external override returns (uint256, uint256) {
        uint256 p = wdiv(initialY, initialX);
        slots[0] = BASE_FEE; slots[1] = BASE_FEE; slots[2] = 0; slots[3] = WAD; slots[4] = 0;
        slots[5] = p; slots[6] = 950000000000000; slots[7] = 800000000000000000;
        slots[8] = 2000000000000000; slots[9] = 0; slots[10] = 0;
        slots[11] = 0; slots[12] = 0; slots[13] = MAX_FEE_CAP; slots[14] = p;
        return (BASE_FEE, BASE_FEE);
    }

    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 prevBidFee = slots[0];
        uint256 prevAskFee = slots[1];
        uint256 lastTs = slots[2];
        uint256 dirState = slots[3];
        uint256 actEma = slots[4];
        uint256 pHat = slots[5];
        uint256 sigmaHat = slots[6];
        uint256 lambdaHat = slots[7];
        uint256 sizeHat = slots[8];
        uint256 toxEma = slots[9];
        uint256 stepTradeCount = slots[10];

        // --- New step ---
        if (trade.timestamp > lastTs) {
            uint256 elapsedRaw = trade.timestamp - lastTs;
            uint256 elapsed = elapsedRaw > ELAPSED_CAP ? ELAPSED_CAP : elapsedRaw;
            dirState = _decayCentered(dirState, DIR_DECAY, elapsed);
            actEma = wmul(actEma, _powWad(ACT_DECAY, elapsed));
            sizeHat = wmul(sizeHat, _powWad(SIZE_DECAY, elapsed));
            toxEma = wmul(toxEma, _powWad(TOX_DECAY, elapsed));
            if (stepTradeCount > 0 && elapsedRaw > 0) {
                uint256 lambdaInst = (stepTradeCount * WAD) / elapsedRaw;
                if (lambdaInst > LAMBDA_CAP) lambdaInst = LAMBDA_CAP;
                lambdaHat = wmul(lambdaHat, LAMBDA_DECAY) + wmul(lambdaInst, WAD - LAMBDA_DECAY);
            }
            // dynamic fee cap
            {
                uint256 cap = MAX_FEE_CAP - wmul(sigmaHat, CAP_SIGMA_SENSITIVITY);
                slots[13] = cap < MIN_FEE_CAP ? MIN_FEE_CAP : cap;
            }
            stepTradeCount = 0;
        }

        bool firstInStep = stepTradeCount == 0;
        uint256 spot = trade.reserveX > 0 ? wdiv(trade.reserveY, trade.reserveX) : pHat;
        if (pHat == 0) pHat = spot;

        uint256 feeUsed = trade.isBuy ? prevBidFee : prevAskFee;
        uint256 gamma = feeUsed < WAD ? WAD - feeUsed : 0;
        uint256 pImplied = gamma == 0 ? spot : (trade.isBuy ? wmul(spot, gamma) : wdiv(spot, gamma));

        // --- Update pHat ---
        {
            uint256 ret = pHat > 0 ? wdiv(absDiff(pImplied, pHat), pHat) : 0;
            uint256 alpha = firstInStep ? PHAT_ALPHA : PHAT_ALPHA_RETAIL;
            uint256 adaptiveGate = wmul(sigmaHat, GATE_SIGMA_MULT);
            if (adaptiveGate < MIN_GATE) adaptiveGate = MIN_GATE;
            if (ret <= adaptiveGate) pHat = wmul(pHat, WAD - alpha) + wmul(pImplied, alpha);
            if (firstInStep) {
                if (ret > RET_CAP) ret = RET_CAP;
                sigmaHat = wmul(sigmaHat, SIGMA_DECAY) + wmul(ret, WAD - SIGMA_DECAY);
            }
        }

        // --- Step state ---
        uint256 tradeRatio = trade.reserveY > 0 ? wdiv(trade.amountY, trade.reserveY) : 0;
        if (tradeRatio > TRADE_RATIO_CAP) tradeRatio = TRADE_RATIO_CAP;

        if (tradeRatio > SIGNAL_THRESHOLD) {
            uint256 push = tradeRatio * DIR_IMPACT_MULT;
            if (push > WAD / 4) push = WAD / 4;
            if (trade.isBuy) {
                dirState = dirState + push;
                if (dirState > 2 * WAD) dirState = 2 * WAD;
            } else {
                dirState = dirState > push ? dirState - push : 0;
            }
            actEma = wmul(actEma, ACT_BLEND_DECAY) + wmul(tradeRatio, WAD - ACT_BLEND_DECAY);
            sizeHat = wmul(sizeHat, SIZE_BLEND_DECAY) + wmul(tradeRatio, WAD - SIZE_BLEND_DECAY);
            if (sizeHat > WAD) sizeHat = WAD;
        }

        // --- Toxicity ---
        uint256 tox = pHat > 0 ? wdiv(absDiff(spot, pHat), pHat) : 0;
        if (tox > TOX_CAP) tox = TOX_CAP;
        toxEma = wmul(toxEma, TOX_BLEND_DECAY) + wmul(tox, WAD - TOX_BLEND_DECAY);
        uint256 toxSignal = toxEma;

        // --- Trade classification ---
        uint256 lastSide = slots[11];
        uint256 consecCount = slots[12];
        uint256 cSide = trade.isBuy ? 1 : 0;
        if (cSide == lastSide && stepTradeCount > 0) consecCount += 1; else consecCount = 1;

        // --- Fee model ---
        uint256 fMid;
        {
            uint256 flowSize = wmul(lambdaHat, sizeHat);
            uint256 fBase = BASE_FEE + wmul(SIGMA_COEF, sigmaHat) + wmul(LAMBDA_COEF, lambdaHat) + wmul(FLOW_SIZE_COEF, flowSize);
            uint256 toxSq = wmul(toxSignal, toxSignal);
            uint256 fTox = wmul(TOX_LINEAR_COEF, toxSignal) + wmul(TOX_QUAD_COEF, toxSq);
            uint256 fAct = wmul(ACT_COEF, actEma);
            uint256 fSigmaTox = wmul(SIGMA_TOX_COEF, wmul(sigmaHat, toxSignal));
            fMid = fBase + fTox + fAct + fSigmaTox;
        }

        // --- Directional skew ---
        uint256 dirDev = dirState >= WAD ? dirState - WAD : WAD - dirState;
        bool sellPressure = dirState >= WAD;
        uint256 dirSkew = wmul(DIR_LINEAR_COEF, dirDev) + wmul(DIR_TOX_COEF, wmul(dirDev, toxSignal));

        // --- Apply directional skew ---
        uint256 bidFee;
        uint256 askFee;
        if (sellPressure) {
            bidFee = fMid + dirSkew;
            askFee = fMid > dirSkew ? fMid - dirSkew : 0;
        } else {
            askFee = fMid + dirSkew;
            bidFee = fMid > dirSkew ? fMid - dirSkew : 0;
        }

        // --- Stale price protection (match Search strategy exactly) ---
        {
            uint256 staleShift = wmul(STALE_DIR_COEF, toxSignal);
            uint256 attractShift = wmul(staleShift, STALE_ATTRACT_FRAC);
            if (spot >= pHat) {
                bidFee = bidFee + staleShift;
                askFee = askFee > attractShift ? askFee - attractShift : 0;
            } else {
                askFee = askFee + staleShift;
                bidFee = bidFee > attractShift ? bidFee - attractShift : 0;
            }
        }

        // --- Trade-aligned toxicity boost ---
        {
            bool tradeAligned = (trade.isBuy && spot >= pHat) || (!trade.isBuy && spot < pHat);
            if (tradeAligned) {
                uint256 tradeBoost = wmul(TRADE_TOX_BOOST, tradeRatio);
                if (trade.isBuy) bidFee = bidFee + tradeBoost;
                else askFee = askFee + tradeBoost;
            }
        }

        // --- Asymmetric tail compression ---
        if (sellPressure) {
            bidFee = clampFee(_compressTail(bidFee, TAIL_SLOPE_PROTECT));
            askFee = clampFee(_compressTail(askFee, TAIL_SLOPE_ATTRACT));
        } else {
            askFee = clampFee(_compressTail(askFee, TAIL_SLOPE_PROTECT));
            bidFee = clampFee(_compressTail(bidFee, TAIL_SLOPE_ATTRACT));
        }

        // --- Apply dynamic fee cap ---
        uint256 dynamicFeeCap = slots[13];
        bidFee = bidFee > dynamicFeeCap ? dynamicFeeCap : bidFee;
        askFee = askFee > dynamicFeeCap ? dynamicFeeCap : askFee;
        bidFee = clamp(bidFee, BASE_FEE, MAX_FEE_CAP);
        askFee = clamp(askFee, BASE_FEE, MAX_FEE_CAP);

        // --- Store state ---
        slots[0] = bidFee; slots[1] = askFee; slots[2] = trade.timestamp;
        slots[3] = dirState; slots[4] = actEma; slots[5] = pHat;
        slots[6] = sigmaHat; slots[7] = lambdaHat; slots[8] = sizeHat;
        slots[9] = toxEma; slots[10] = stepTradeCount + 1;
        slots[11] = cSide; slots[12] = consecCount; slots[14] = spot;

        return (clampFee(bidFee), clampFee(askFee));
    }

    function _compressTail(uint256 fee, uint256 slope) internal pure returns (uint256) {
        if (fee <= TAIL_KNEE) return fee;
        return TAIL_KNEE + wmul(fee - TAIL_KNEE, slope);
    }

    function _powWad(uint256 factor, uint256 exp) internal pure returns (uint256 result) {
        result = WAD;
        while (exp > 0) {
            if (exp & 1 == 1) result = wmul(result, factor);
            factor = wmul(factor, factor);
            exp >>= 1;
        }
    }

    function _decayCentered(uint256 centered, uint256 decayFactor, uint256 elapsed) internal pure returns (uint256) {
        uint256 mul = _powWad(decayFactor, elapsed);
        if (centered >= WAD) return WAD + wmul(centered - WAD, mul);
        uint256 below = wmul(WAD - centered, mul);
        return below < WAD ? WAD - below : 0;
    }

    function getName() external pure override returns (string memory) {
        return "combo";
    }
}
