import subprocess
import sys

# Test variations around the best params: BF=30, AT=60, LT=250, AB=350, LB=100, D=7, SM=400, SD=5, CB=3
tests = [
    # Test ARB_THR (50, 60, 70)
    {"name": "AT=50", "params": {"at": 50}},
    {"name": "AT=60", "params": {"at": 60}},
    {"name": "AT=70", "params": {"at": 70}},

    # Test LARGE_THR (200, 250, 300)
    {"name": "LT=200", "params": {"lt": 200}},
    {"name": "LT=250", "params": {"lt": 250}},
    {"name": "LT=300", "params": {"lt": 300}},

    # Test ARB_BUMP (300, 350, 400)
    {"name": "AB=300", "params": {"ab": 300}},
    {"name": "AB=350", "params": {"ab": 350}},
    {"name": "AB=400", "params": {"ab": 400}},

    # Test LARGE_BUMP (80, 100, 120)
    {"name": "LB=80", "params": {"lb": 80}},
    {"name": "LB=100", "params": {"lb": 100}},
    {"name": "LB=120", "params": {"lb": 120}},

    # Test DECAY (5, 6, 7, 8)
    {"name": "D=5", "params": {"d": 5}},
    {"name": "D=6", "params": {"d": 6}},
    {"name": "D=7", "params": {"d": 7}},
    {"name": "D=8", "params": {"d": 8}},

    # Test CONSEC_BUMP (2, 3, 4)
    {"name": "CB=2", "params": {"cb": 2}},
    {"name": "CB=3", "params": {"cb": 3}},
    {"name": "CB=4", "params": {"cb": 4}},

    # Test SKEW_MAX (350, 400, 450)
    {"name": "SM=350", "params": {"sm": 350}},
    {"name": "SM=400", "params": {"sm": 400}},
    {"name": "SM=450", "params": {"sm": 450}},

    # Test SKEW_DECAY (4, 5, 6)
    {"name": "SD=4", "params": {"sd": 4}},
    {"name": "SD=5", "params": {"sd": 5}},
    {"name": "SD=6", "params": {"sd": 6}},

    # Test BASE_FEE (25, 30, 35)
    {"name": "BF=25", "params": {"bf": 25}},
    {"name": "BF=30", "params": {"bf": 30}},
    {"name": "BF=35", "params": {"bf": 35}},
]

# Default params
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

best = 0
best_name = ""

for test in tests:
    # Merge params
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