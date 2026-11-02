import subprocess
import sys

# Test combinations of best params
# Best single params: AT=70 (460.57), CB=2 (460.51)
tests = [
    {"name": "AT=70,CB=2", "params": {"at": 70, "cb": 2}},
    {"name": "AT=70,CB=3", "params": {"at": 70, "cb": 3}},
    {"name": "AT=60,CB=2", "params": {"at": 60, "cb": 2}},

    # Also test some other promising combos
    {"name": "AT=70,D=6", "params": {"at": 70, "d": 6}},
    {"name": "AT=70,D=8", "params": {"at": 70, "d": 8}},
    {"name": "AT=70,SM=450", "params": {"at": 70, "sm": 450}},
    {"name": "AT=70,SD=4", "params": {"at": 70, "sd": 4}},

    # Test BF=25 which was worse but maybe with other params
    {"name": "BF=25,AT=70", "params": {"bf": 25, "at": 70}},
    {"name": "BF=35,AT=70", "params": {"bf": 35, "at": 70}},

    # Test LT variations with AT=70
    {"name": "AT=70,LT=200", "params": {"at": 70, "lt": 200}},
    {"name": "AT=70,LT=300", "params": {"at": 70, "lt": 300}},

    # Test AB variations with AT=70
    {"name": "AT=70,AB=400", "params": {"at": 70, "ab": 400}},
    {"name": "AT=70,AB=300", "params": {"at": 70, "ab": 300}},
]

# Default params (baseline best)
defaults = {"bf": 30, "at": 60, "lt": 250, "ab": 350, "lb": 100, "cb": 3, "d": 7, "sm": 400, "sd": 5}

template = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";
contract Strategy is AMMStrategyBase {{
    uint256 internal constant BASE_FEE = {bf} * BPS;
    uint256 internal constant FEE_FLOOR = 10 * BPS;
    uint256 internal constant FEE_CAP = 500 * BPS;
    uint256 internal constant ARB_THR = WAD / {at};
    uint256 internal constant LARGE_THR = WAD / {lt};
    uint256 internal constant ARB_BUMP = {ab} * BPS;
    uint256 internal constant LARGE_BUMP = {lb} * BPS;
    uint256 internal constant CONSEC_BUMP = {cb} * BPS;
    uint256 internal constant DECAY = {d} * BPS;
    uint256 internal constant SKEW_MAX = {sm} * BPS;
    uint256 internal constant SKEW_DECAY = {sd};
    uint256 internal constant NONE = type(uint256).max;

    function afterInitialize(uint256, uint256) external override returns (uint256, uint256) {{
        slots[0] = NONE; slots[3] = WAD;
        slots[6] = BASE_FEE; slots[7] = BASE_FEE;
        slots[8] = 0; slots[9] = 0; slots[10] = 0;
        slots[14] = BASE_FEE; slots[15] = BASE_FEE;
        return (BASE_FEE, BASE_FEE);
    }}

    function afterSwap(TradeInfo calldata t) external override returns (uint256, uint256) {{
        uint256 lastTs = slots[0]; uint256 invSkew = slots[3];
        uint256 bid = slots[6]; uint256 ask = slots[7];
        uint256 tc = slots[8]; uint256 ls = slots[9]; uint256 cs = slots[10];
        uint256 elapsed = (lastTs == NONE || t.timestamp > lastTs) ? (lastTs == NONE ? 1 : t.timestamp - lastTs) : 0;
        if (elapsed > 0) {{ tc = 0; }} else {{ tc += 1; }}
        if (elapsed > 0) {{
            if (invSkew > WAD) invSkew = invSkew - (invSkew - WAD) / SKEW_DECAY;
            else if (invSkew < WAD) invSkew = invSkew + (WAD - invSkew) / SKEW_DECAY;
        }}

        uint256 tr = wdiv(t.amountY, t.reserveY);
        bool isBuy = t.isBuy;
        bool isArb = tr > ARB_THR; bool isLg = tr > LARGE_THR;
        uint256 cSide = isBuy ? 1 : 0;
        if (cSide == ls && tc > 1) cs += 1; else cs = 1;
        slots[9] = cSide; slots[10] = cs;

        if (isBuy) {{
            invSkew = invSkew + wmul(invSkew, tr);
            if (invSkew > WAD * 5) invSkew = WAD * 5;
        }} else {{
            uint256 dec = wmul(invSkew, tr);
            invSkew = invSkew > dec ? invSkew - dec : WAD / 5;
        }}
        slots[3] = invSkew;

        if (isArb) {{ if (isBuy) ask = ask + ARB_BUMP > FEE_CAP ? FEE_CAP : ask + ARB_BUMP; else bid = bid + ARB_BUMP > FEE_CAP ? FEE_CAP : bid + ARB_BUMP; }}
        else if (isLg) {{ if (isBuy) ask = ask + LARGE_BUMP > FEE_CAP ? FEE_CAP : ask + LARGE_BUMP; else bid = bid + LARGE_BUMP > FEE_CAP ? FEE_CAP : bid + LARGE_BUMP; }}
        if (cs >= 3) {{ uint256 bump = (cs - 2) * CONSEC_BUMP; if (cSide == 1) {{ bid = bid + bump > FEE_CAP ? FEE_CAP : bid + bump; }} else {{ ask = ask + bump > FEE_CAP ? FEE_CAP : ask + bump; }} }}

        if (invSkew > WAD) {{
            uint256 skew = wmul(SKEW_MAX, (invSkew - WAD) / invSkew);
            if (ask > skew) ask = ask - skew; else ask = FEE_FLOOR;
            bid = bid + skew > FEE_CAP ? FEE_CAP : bid + skew;
            bid = bid + skew / 2 > FEE_CAP ? FEE_CAP : bid + skew / 2;
        }} else if (invSkew < WAD) {{
            uint256 skew = wmul(SKEW_MAX, (WAD - invSkew) / WAD);
            if (bid > skew) bid = bid - skew; else bid = FEE_FLOOR;
            ask = ask + skew > FEE_CAP ? FEE_CAP : ask + skew;
            ask = ask + skew / 2 > FEE_CAP ? FEE_CAP : ask + skew / 2;
        }}

        uint256 targetBid = BASE_FEE; uint256 targetAsk = BASE_FEE;
        if (invSkew > WAD) {{
            uint256 skew = wmul(SKEW_MAX, (invSkew - WAD) / invSkew);
            if (targetAsk > skew) targetAsk = targetAsk - skew; else targetAsk = FEE_FLOOR;
            targetBid = targetBid + skew > FEE_CAP ? FEE_CAP : targetBid + skew;
            targetBid = targetBid + skew / 2 > FEE_CAP ? FEE_CAP : targetBid + skew / 2;
        }} else if (invSkew < WAD) {{
            uint256 skew = wmul(SKEW_MAX, (WAD - invSkew) / WAD);
            if (targetBid > skew) targetBid = targetBid - skew; else targetBid = FEE_FLOOR;
            targetAsk = targetAsk + skew > FEE_CAP ? FEE_CAP : targetAsk + skew;
            targetAsk = targetAsk + skew / 2 > FEE_CAP ? FEE_CAP : targetAsk + skew / 2;
        }}
        if (isArb) {{ if (isBuy) targetAsk = targetAsk + ARB_BUMP > FEE_CAP ? FEE_CAP : targetAsk + ARB_BUMP; else targetBid = targetBid + ARB_BUMP > FEE_CAP ? FEE_CAP : targetBid + ARB_BUMP; }}

        if (elapsed > 0) {{ uint256 d = elapsed * DECAY; bid = _toward(bid, targetBid, d); ask = _toward(ask, targetAsk, d); }}
        bid = clamp(bid, FEE_FLOOR, FEE_CAP); ask = clamp(ask, FEE_FLOOR, FEE_CAP);
        slots[0] = t.timestamp; slots[3] = invSkew; slots[6] = bid; slots[7] = ask; slots[8] = tc; slots[14] = bid; slots[15] = ask;
        return (clampFee(bid), clampFee(ask));
    }}
    function getName() external pure override returns (string memory) {{ return "Test"; }}
    function _toward(uint256 v, uint256 t, uint256 s) internal pure returns (uint256) {{ if (v > t) return v - t > s ? v - s : t; if (v < t) return t - v > s ? v + s : t; return v; }}
}}'''

best = 460.57
best_name = "AT=70"

for test in tests:
    params = defaults.copy()
    params.update(test["params"])

    code = template.format(**params)
    with open('/Users/ezhang/Documents/amm-challenge/contracts/src/Strategy.sol', 'w') as f:
        f.write(code)

    result = subprocess.run(
        ['python', '-u', '-m', 'amm_competition.cli', 'run', 'contracts/src/Strategy.sol', '--simulations', '50'],
        capture_output=True, text=True, cwd='/Users/ezhang/Documents/amm-challenge', timeout=180
    )

    edge = None
    for line in result.stdout.split('\n'):
        if 'Edge:' in line:
            edge = float(line.split('Edge:')[1].strip())
            break

    if edge:
        status = "BEST" if edge > best else ""
        if edge > best:
            best = edge
            best_name = test["name"]
        print(f"{test['name']}: {edge:.2f} {status}")
    else:
        print(f"{test['name']}: FAILED")
        if result.stderr:
            print(f"  {result.stderr[:200]}")

print(f"\nBest: {best_name} = {best:.2f}")