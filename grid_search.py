import subprocess
import itertools

params = {
    'BASE_FEE': [55, 60, 65],
    'ARB_BUMP': [220, 250, 280],
    'LARGE_BUMP': [80, 90, 100],
    'CONSEC_BUMP': [2, 3, 4],
}

best = 0
best_combo = None

for bf, ab, lb, cb in itertools.product(params['BASE_FEE'], params['ARB_BUMP'], params['LARGE_BUMP'], params['CONSEC_BUMP']):
    code = f'''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BASE_FEE = {bf} * BPS;
    uint256 internal constant FEE_FLOOR = 10 * BPS;
    uint256 internal constant FEE_CAP = 500 * BPS;
    uint256 internal constant ARB_THR = WAD / 50;
    uint256 internal constant LARGE_THR = WAD / 150;
    uint256 internal constant ARB_BUMP = {ab} * BPS;
    uint256 internal constant LARGE_BUMP = {lb} * BPS;
    uint256 internal constant CONSEC_BUMP = {cb} * BPS;
    uint256 internal constant DECAY = 1 * BPS;
    uint256 internal constant NONE = type(uint256).max;

    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        slots[0] = NONE; slots[6] = BASE_FEE; slots[7] = BASE_FEE;
        slots[8] = 0; slots[9] = 0; slots[10] = 0;
        slots[14] = BASE_FEE; slots[15] = BASE_FEE;
        return (BASE_FEE, BASE_FEE);
    }}

    function afterSwap(TradeInfo calldata t) external override returns (uint256, uint256) {{
        uint256 lastTs = slots[0];
        uint256 bid = slots[6]; uint256 ask = slots[7];
        uint256 tc = slots[8]; uint256 ls = slots[9]; uint256 cs = slots[10];
        uint256 elapsed = (lastTs == NONE || t.timestamp > lastTs) ? (lastTs == NONE ? 1 : t.timestamp - lastTs) : 0;
        if (elapsed > 0) {{ tc = 0; }} else {{ tc += 1; }}

        uint256 tr = wdiv(t.amountY, t.reserveY);
        bool isBuy = t.isBuy;
        bool isArb = tr > ARB_THR; bool isLg = tr > LARGE_THR;
        uint256 cSide = isBuy ? 1 : 0;
        if (cSide == ls && tc > 1) cs += 1; else cs = 1;
        slots[9] = cSide; slots[10] = cs;

        if (isArb) {{ if (isBuy) ask = ask + ARB_BUMP > FEE_CAP ? FEE_CAP : ask + ARB_BUMP; else bid = bid + ARB_BUMP > FEE_CAP ? FEE_CAP : bid + ARB_BUMP; }}
        else if (isLg) {{ if (isBuy) ask = ask + LARGE_BUMP > FEE_CAP ? FEE_CAP : ask + LARGE_BUMP; else bid = bid + LARGE_BUMP > FEE_CAP ? FEE_CAP : bid + LARGE_BUMP; }}
        if (cs >= 3) {{ uint256 bump = (cs - 2) * CONSEC_BUMP; if (cSide == 1) {{ bid = bid + bump > FEE_CAP ? FEE_CAP : bid + bump; }} else {{ ask = ask + bump > FEE_CAP ? FEE_CAP : ask + bump; }} }}

        uint256 targetBid = BASE_FEE; uint256 targetAsk = BASE_FEE;
        if (isArb) {{ if (isBuy) targetAsk = targetAsk + ARB_BUMP > FEE_CAP ? FEE_CAP : targetAsk + ARB_BUMP; else targetBid = targetBid + ARB_BUMP > FEE_CAP ? FEE_CAP : targetBid + ARB_BUMP; }}

        if (elapsed > 0) {{ uint256 d = elapsed * DECAY; bid = _toward(bid, targetBid, d); ask = _toward(ask, targetAsk, d); }}
        bid = clamp(bid, FEE_FLOOR, FEE_CAP); ask = clamp(ask, FEE_FLOOR, FEE_CAP);
        slots[0] = t.timestamp; slots[6] = bid; slots[7] = ask; slots[8] = tc; slots[14] = bid; slots[15] = ask;
        return (clampFee(bid), clampFee(ask));
    }}
    function getName() external pure override returns (string memory) {{ return "Grid"; }}
    function _toward(uint256 v, uint256 t, uint256 s) internal pure returns (uint256) {{ if (v > t) return v - t > s ? v - s : t; if (v < t) return t - v > s ? v + s : t; return v; }}
}}
'''
    with open('contracts/src/Strategy.sol', 'w') as f:
        f.write(code)
    
    result = subprocess.run(['python', '-m', 'amm_competition.cli', 'run', 'contracts/src/Strategy.sol', '--simulations', '200'], 
                          capture_output=True, text=True, cwd='/Users/ezhang/Documents/amm-challenge')
    
    for line in result.stdout.split('\n'):
        if 'Edge:' in line:
            edge = float(line.split('Edge:')[1].strip())
            print(f"BF={bf} AB={ab} LB={lb} CB={cb} -> {edge}")
            if edge > best:
                best = edge
                best_combo = (bf, ab, lb, cb)
            break

print(f"\nBest: BF={best_combo[0]} AB={best_combo[1]} LB={best_combo[2]} CB={best_combo[3]} -> {best}")
