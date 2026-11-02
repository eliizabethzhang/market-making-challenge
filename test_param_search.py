import subprocess
import sys

# Focused parameter search around best of yq and category.xyz
tests = [
    # yq baseline
    {"name": "yq_baseline", "params": {}},

    # category.xyz baseline
    {"name": "cat_baseline", "params": {
        "st": "WAD / 650", "dd": "750000000000000000", "ad": "530000000000000000",
        "sd": "530000000000000000", "sdecay": "690000000000000000",
        "sbld": "828000000000000000", "tbld": "51000000000000000", "abld": "985000000000000000",
        "pa": "270000000000000000", "par": "60000000000000000", "dim": "4",
        "gsm": "7200000000000000000", "tcc": "20000 * BPS", "ttb": "3500 * BPS",
        "saf": "1050000000000000000", "rc": "WAD / 35", "lc": "1820000000000000000",
        "bf": "4", "tc": "300", "tqc": "15000", "tnk": "600", "tsp": "930000000000000000",
        "tsa": "850000000000000000"
    }},

    # Hybrid: yq decay params + cat signal params
    {"name": "hybrid1", "params": {
        "st": "WAD / 650", "dd": "800000000000000000", "ad": "700000000000000000",
        "sd": "700000000000000000", "sdecay": "824000000000000000",
        "sbld": "818000000000000000", "tbld": "51000000000000000", "abld": "985000000000000000",
        "pa": "260000000000000000", "par": "50000000000000000", "dim": "4",
        "gsm": "10 * WAD", "tcc": "15000 * BPS", "ttb": "2500 * BPS",
        "saf": "1124000000000000000", "rc": "WAD / 10", "lc": "5 * WAD",
        "bf": "3", "tc": "250", "tqc": "11700", "tnk": "500", "tsp": "930000000000000000",
        "tsa": "955000000000000000"
    }},

    # Hybrid: cat decay params + yq signal params
    {"name": "hybrid2", "params": {
        "st": "WAD / 500", "dd": "750000000000000000", "ad": "530000000000000000",
        "sd": "530000000000000000", "sdecay": "690000000000000000",
        "sbld": "828000000000000000", "tbld": "51000000000000000", "abld": "985000000000000000",
        "pa": "270000000000000000", "par": "60000000000000000", "dim": "2",
        "gsm": "7200000000000000000", "tcc": "20000 * BPS", "ttb": "3500 * BPS",
        "saf": "1050000000000000000", "rc": "WAD / 35", "lc": "1820000000000000000",
        "bf": "4", "tc": "300", "tqc": "15000", "tnk": "600", "tsp": "930000000000000000",
        "tsa": "850000000000000000"
    }},

    # Tighter signal threshold
    {"name": "tight_signal_400", "params": {"st": "WAD / 400"}},
    {"name": "tight_signal_600", "params": {"st": "WAD / 600"}},
    {"name": "tight_signal_700", "params": {"st": "WAD / 700"}},
    {"name": "tight_signal_800", "params": {"st": "WAD / 800"}},

    # DIR_IMPACT_MULT variations
    {"name": "dim_3", "params": {"dim": "3"}},
    {"name": "dim_5", "params": {"dim": "5"}},

    # GATE_SIGMA_MULT variations
    {"name": "gsm_8", "params": {"gsm": "8 * WAD"}},
    {"name": "gsm_9", "params": {"gsm": "9 * WAD"}},
    {"name": "gsm_11", "params": {"gsm": "11 * WAD"}},
    {"name": "gsm_12", "params": {"gsm": "12 * WAD"}},

    # RET_CAP variations
    {"name": "rc_15", "params": {"rc": "WAD / 15"}},
    {"name": "rc_20", "params": {"rc": "WAD / 20"}},
    {"name": "rc_25", "params": {"rc": "WAD / 25"}},
    {"name": "rc_30", "params": {"rc": "WAD / 30"}},

    # BASE_FEE variations
    {"name": "bf_2", "params": {"bf": "2"}},
    {"name": "bf_5", "params": {"bf": "5"}},

    # TOX_COEF variations
    {"name": "tc_200", "params": {"tc": "200"}},
    {"name": "tc_275", "params": {"tc": "275"}},
    {"name": "tc_325", "params": {"tc": "325"}},
    {"name": "tc_350", "params": {"tc": "350"}},

    # TOX_QUAD_COEF variations
    {"name": "tqc_10000", "params": {"tqc": "10000"}},
    {"name": "tqc_13000", "params": {"tqc": "13000"}},
    {"name": "tqc_17000", "params": {"tqc": "17000"}},
    {"name": "tqc_18000", "params": {"tqc": "18000"}},
    {"name": "tqc_22000", "params": {"tqc": "22000"}},

    # TOX_CUBIC_COEF variations
    {"name": "tcc_10000", "params": {"tcc": "10000 * BPS"}},
    {"name": "tcc_12000", "params": {"tcc": "12000 * BPS"}},
    {"name": "tcc_18000", "params": {"tcc": "18000 * BPS"}},
    {"name": "tcc_25000", "params": {"tcc": "25000 * BPS"}},

    # TRADE_TOX_BOOST variations
    {"name": "ttb_2000", "params": {"ttb": "2000 * BPS"}},
    {"name": "ttb_3000", "params": {"ttb": "3000 * BPS"}},
    {"name": "ttb_4000", "params": {"ttb": "4000 * BPS"}},

    # STALE_ATTRACT_FRAC variations
    {"name": "saf_1.0", "params": {"saf": "1000000000000000000"}},
    {"name": "saf_1.1", "params": {"saf": "1100000000000000000"}},
    {"name": "saf_1.15", "params": {"saf": "1150000000000000000"}},

    # TAIL_KNEE variations
    {"name": "tnk_400", "params": {"tnk": "400"}},
    {"name": "tnk_550", "params": {"tnk": "550"}},
    {"name": "tnk_700", "params": {"tnk": "700"}},

    # TAIL_SLOPE_ATTRACT variations
    {"name": "tsa_0.8", "params": {"tsa": "800000000000000000"}},
    {"name": "tsa_0.825", "params": {"tsa": "825000000000000000"}},
    {"name": "tsa_0.875", "params": {"tsa": "875000000000000000"}},
    {"name": "tsa_0.9", "params": {"tsa": "900000000000000000"}},
    {"name": "tsa_0.925", "params": {"tsa": "925000000000000000"}},
]

# Default parameters from yq
defaults = {
    "st": "WAD / 500", "dd": "800000000000000000", "ad": "700000000000000000",
    "sd": "700000000000000000", "sdecay": "824000000000000000",
    "sbld": "818000000000000000", "tbld": "51000000000000000", "abld": "985000000000000000",
    "pa": "260000000000000000", "par": "50000000000000000", "dim": "2",
    "gsm": "10 * WAD", "tcc": "15000 * BPS", "ttb": "2500 * BPS",
    "saf": "1124000000000000000", "rc": "WAD / 10", "lc": "5 * WAD",
    "bf": "3", "tc": "250", "tqc": "11700", "tnk": "500", "tsp": "930000000000000000",
    "tsa": "955000000000000000"
}

# Use double braces for Solidity braces
template = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{TradeInfo}} from "./IAMMStrategy.sol";

contract Strategy is AMMStrategyBase {{
    uint256 constant ELAPSED_CAP = 8;
    uint256 constant SIGNAL_THRESHOLD = {st};
    uint256 constant DIR_DECAY = {dd};
    uint256 constant ACT_DECAY = {ad};
    uint256 constant SIZE_DECAY = {sd};
    uint256 constant TOX_DECAY = 910000000000000000;
    uint256 constant SIGMA_DECAY = {sdecay};
    uint256 constant LAMBDA_DECAY = 990000000000000000;
    uint256 constant SIZE_BLEND_DECAY = {sbld};
    uint256 constant TOX_BLEND_DECAY = {tbld};
    uint256 constant ACT_BLEND_DECAY = {abld};
    uint256 constant PHAT_ALPHA = {pa};
    uint256 constant PHAT_ALPHA_RETAIL = {par};
    uint256 constant DIR_IMPACT_MULT = {dim};
    uint256 constant GATE_SIGMA_MULT = {gsm};
    uint256 constant MIN_GATE = 30000000000000000;
    uint256 constant TOX_CUBIC_COEF = {tcc};
    uint256 constant TRADE_TOX_BOOST = {ttb};
    uint256 constant STALE_ATTRACT_FRAC = {saf};
    uint256 constant RET_CAP = {rc};
    uint256 constant TOX_CAP = WAD / 5;
    uint256 constant TRADE_RATIO_CAP = WAD / 5;
    uint256 constant LAMBDA_CAP = {lc};
    uint256 constant STEP_COUNT_CAP = 64;
    uint256 constant BASE_FEE = {bf} * BPS;
    uint256 constant SIGMA_COEF = 200000000000000000;
    uint256 constant LAMBDA_COEF = 12 * BPS;
    uint256 constant FLOW_SIZE_COEF = 4842 * BPS;
    uint256 constant TOX_COEF = {tc} * BPS;
    uint256 constant TOX_QUAD_COEF = {tqc} * BPS;
    uint256 constant ACT_COEF = 91843 * BPS;
    uint256 constant DIR_COEF = 20 * BPS;
    uint256 constant DIR_TOX_COEF = 100 * BPS;
    uint256 constant STALE_DIR_COEF = 6850 * BPS;
    uint256 constant SIGMA_TOX_COEF = 500 * BPS;
    uint256 constant TAIL_KNEE = {tnk} * BPS;
    uint256 constant TAIL_SLOPE_PROTECT = {tsp};
    uint256 constant TAIL_SLOPE_ATTRACT = {tsa};

    function afterInitialize(uint256 initialX, uint256 initialY) external override returns (uint256, uint256) {{
        slots[0] = BASE_FEE; slots[1] = BASE_FEE; slots[2] = 0; slots[3] = WAD; slots[4] = 0;
        slots[5] = initialX > 0 ? wdiv(initialY, initialX) : 100 * WAD;
        slots[6] = 950000000000000; slots[7] = 800000000000000000; slots[8] = 2000000000000000;
        slots[9] = 0; slots[10] = 0;
        return (BASE_FEE, BASE_FEE);
    }}

    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {{
        uint256 prevBidFee = slots[0]; uint256 prevAskFee = slots[1]; uint256 lastTs = slots[2];
        uint256 dirState = slots[3]; uint256 actEma = slots[4]; uint256 pHat = slots[5];
        uint256 sigmaHat = slots[6]; uint256 lambdaHat = slots[7]; uint256 sizeHat = slots[8];
        uint256 toxEma = slots[9]; uint256 stepTradeCount = slots[10];

        bool isNewStep = trade.timestamp > lastTs;
        if (isNewStep) {{
            uint256 elapsedRaw = trade.timestamp - lastTs;
            uint256 elapsed = elapsedRaw > ELAPSED_CAP ? ELAPSED_CAP : elapsedRaw;
            dirState = _decayCentered(dirState, DIR_DECAY, elapsed);
            actEma = wmul(actEma, _powWad(ACT_DECAY, elapsed));
            sizeHat = wmul(sizeHat, _powWad(SIZE_DECAY, elapsed));
            toxEma = wmul(toxEma, _powWad(TOX_DECAY, elapsed));
            if (stepTradeCount > 0 && elapsedRaw > 0) {{
                uint256 lambdaInst = (stepTradeCount * WAD) / elapsedRaw;
                if (lambdaInst > LAMBDA_CAP) lambdaInst = LAMBDA_CAP;
                lambdaHat = wmul(lambdaHat, LAMBDA_DECAY) + wmul(lambdaInst, WAD - LAMBDA_DECAY);
            }}
            stepTradeCount = 0;
        }}

        bool firstInStep = stepTradeCount == 0;
        uint256 spot = trade.reserveX > 0 ? wdiv(trade.reserveY, trade.reserveX) : pHat;
        if (pHat == 0) pHat = spot;

        uint256 feeUsed = trade.isBuy ? prevBidFee : prevAskFee;
        uint256 gamma = feeUsed < WAD ? WAD - feeUsed : 0;
        uint256 pImplied;
        if (gamma == 0) {{ pImplied = spot; }}
        else {{ pImplied = trade.isBuy ? wmul(spot, gamma) : wdiv(spot, gamma); }}

        {{
            uint256 ret = pHat > 0 ? wdiv(absDiff(pImplied, pHat), pHat) : 0;
            uint256 alpha = firstInStep ? PHAT_ALPHA : PHAT_ALPHA_RETAIL;
            uint256 adaptiveGate = wmul(sigmaHat, GATE_SIGMA_MULT);
            if (adaptiveGate < MIN_GATE) adaptiveGate = MIN_GATE;
            if (ret <= adaptiveGate) {{ pHat = wmul(pHat, WAD - alpha) + wmul(pImplied, alpha); }}
            if (firstInStep) {{
                if (ret > RET_CAP) ret = RET_CAP;
                sigmaHat = wmul(sigmaHat, SIGMA_DECAY) + wmul(ret, WAD - SIGMA_DECAY);
            }}
        }}

        uint256 tradeRatio = trade.reserveY > 0 ? wdiv(trade.amountY, trade.reserveY) : 0;
        if (tradeRatio > TRADE_RATIO_CAP) tradeRatio = TRADE_RATIO_CAP;

        if (tradeRatio > SIGNAL_THRESHOLD) {{
            uint256 push = tradeRatio * DIR_IMPACT_MULT;
            if (push > WAD / 4) push = WAD / 4;
            if (trade.isBuy) {{
                dirState = dirState + push;
                if (dirState > 2 * WAD) dirState = 2 * WAD;
            }} else {{
                dirState = dirState > push ? dirState - push : 0;
            }}
            actEma = wmul(actEma, ACT_BLEND_DECAY) + wmul(tradeRatio, WAD - ACT_BLEND_DECAY);
            sizeHat = wmul(sizeHat, SIZE_BLEND_DECAY) + wmul(tradeRatio, WAD - SIZE_BLEND_DECAY);
            if (sizeHat > WAD) sizeHat = WAD;
        }}

        uint256 tox = pHat > 0 ? wdiv(absDiff(spot, pHat), pHat) : 0;
        if (tox > TOX_CAP) tox = TOX_CAP;
        toxEma = wmul(toxEma, TOX_BLEND_DECAY) + wmul(tox, WAD - TOX_BLEND_DECAY);
        uint256 toxSignal = toxEma;

        stepTradeCount = stepTradeCount + 1;
        if (stepTradeCount > STEP_COUNT_CAP) stepTradeCount = STEP_COUNT_CAP;

        uint256 flowSize = wmul(lambdaHat, sizeHat);
        uint256 fBase = BASE_FEE + wmul(SIGMA_COEF, sigmaHat) + wmul(LAMBDA_COEF, lambdaHat) + wmul(FLOW_SIZE_COEF, flowSize);
        uint256 fMid = fBase + wmul(TOX_COEF, toxSignal) + wmul(TOX_QUAD_COEF, wmul(toxSignal, toxSignal)) + wmul(ACT_COEF, actEma);
        fMid = fMid + wmul(SIGMA_TOX_COEF, wmul(sigmaHat, toxSignal));

        {{
            uint256 toxCubed = wmul(toxSignal, wmul(toxSignal, toxSignal));
            fMid = fMid + wmul(TOX_CUBIC_COEF, toxCubed);
        }}

        uint256 dirDev; bool sellPressure;
        if (dirState >= WAD) {{ dirDev = dirState - WAD; sellPressure = true; }}
        else {{ dirDev = WAD - dirState; sellPressure = false; }}

        uint256 skew = wmul(DIR_COEF, dirDev) + wmul(DIR_TOX_COEF, wmul(dirDev, toxSignal));
        uint256 bidFee; uint256 askFee;
        if (sellPressure) {{
            bidFee = fMid + skew;
            askFee = fMid > skew ? fMid - skew : 0;
        }} else {{
            askFee = fMid + skew;
            bidFee = fMid > skew ? fMid - skew : 0;
        }}

        {{
            uint256 staleShift = wmul(STALE_DIR_COEF, toxSignal);
            uint256 attractShift = wmul(staleShift, STALE_ATTRACT_FRAC);
            if (spot >= pHat) {{
                bidFee = bidFee + staleShift;
                askFee = askFee > attractShift ? askFee - attractShift : 0;
            }} else {{
                askFee = askFee + staleShift;
                bidFee = bidFee > attractShift ? bidFee - attractShift : 0;
            }}
        }}

        {{
            bool tradeAligned = (trade.isBuy && spot >= pHat) || (!trade.isBuy && spot < pHat);
            if (tradeAligned) {{
                uint256 tradeBoost = wmul(TRADE_TOX_BOOST, tradeRatio);
                if (trade.isBuy) {{ bidFee = bidFee + tradeBoost; }}
                else {{ askFee = askFee + tradeBoost; }}
            }}
        }}

        if (sellPressure) {{
            bidFee = clampFee(_compressTailWithSlope(bidFee, TAIL_SLOPE_PROTECT));
            askFee = clampFee(_compressTailWithSlope(askFee, TAIL_SLOPE_ATTRACT));
        }} else {{
            askFee = clampFee(_compressTailWithSlope(askFee, TAIL_SLOPE_PROTECT));
            bidFee = clampFee(_compressTailWithSlope(bidFee, TAIL_SLOPE_ATTRACT));
        }}

        slots[0] = bidFee; slots[1] = askFee; slots[2] = trade.timestamp;
        slots[3] = dirState; slots[4] = actEma; slots[5] = pHat;
        slots[6] = sigmaHat; slots[7] = lambdaHat; slots[8] = sizeHat;
        slots[9] = toxEma; slots[10] = stepTradeCount;

        return (bidFee, askFee);
    }}

    function _compressTailWithSlope(uint256 fee, uint256 slope) internal pure returns (uint256) {{
        if (fee <= TAIL_KNEE) return fee;
        return TAIL_KNEE + wmul(fee - TAIL_KNEE, slope);
    }}

    function _powWad(uint256 factor, uint256 exp) internal pure returns (uint256 result) {{
        result = WAD;
        while (exp > 0) {{
            if (exp & 1 == 1) result = wmul(result, factor);
            factor = wmul(factor, factor);
            exp >>= 1;
        }}
    }}

    function _decayCentered(uint256 centered, uint256 decayFactor, uint256 elapsed) internal pure returns (uint256) {{
        uint256 mul = _powWad(decayFactor, elapsed);
        if (centered >= WAD) {{ return WAD + wmul(centered - WAD, mul); }}
        uint256 below = wmul(WAD - centered, mul);
        return below < WAD ? WAD - below : 0;
    }}

    function getName() external pure override returns (string memory) {{ return "Search"; }}
}}"""

best = 533.43
best_name = "category.xyz"

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