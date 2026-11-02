import subprocess
import sys

# Test BASE and THETA combinations
base_values = [25, 30, 35, 40, 50, 60]
theta_values = [0, 5e17, 8e17, 1e18]

template = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {{AMMStrategyBase}} from "./AMMStrategyBase.sol";
import {{IAMMStrategy, TradeInfo}} from "./IAMMStrategy.sol";

/// @title Fair-Centered Quoting
/// @notice Fees linear in (pool price - estimated fair price), so marginal quotes stay
///         roughly symmetric around fair. THETA = 0 reduces to a fixed fee at BASE.
contract Strategy is AMMStrategyBase {{
    uint256 internal constant NONE = type(uint256).max;

    uint256 internal constant BASE = {base} * BPS;   // sweep first
    uint256 internal constant THETA = {theta};      // skew strength, WAD (0 to 1e18)
    uint256 internal constant FLOOR = 5 * BPS;
    uint256 internal constant CAP = 150 * BPS;
    uint256 internal constant SIGMA = 1e15;      // per-step vol, 0.10%
    uint256 internal constant K_SIG = 2;         // arb-detection threshold, in sigmas

    // slots[0] = last timestamp, [1] = fair estimate, [2] = last post-trade spot,
    // [3] = bid fee in force, [4] = ask fee in force

    function afterInitialize(uint256 x, uint256 y) external override returns (uint256, uint256) {{
        uint256 p = wdiv(y, x);
        slots[0] = NONE;
        slots[1] = p;
        slots[2] = p;
        slots[3] = BASE;
        slots[4] = BASE;
        return (BASE, BASE);
    }}

    function afterSwap(TradeInfo calldata t) external override returns (uint256, uint256) {{
        uint256 pHat = slots[1];
        uint256 spot0 = slots[2];            // pre-trade spot (only our trades move it)
        uint256 bidF = slots[3];
        uint256 askF = slots[4];
        uint256 spot1 = wdiv(t.reserveY, t.reserveX);

        // Prior uncertainty of fair price since the last update
        uint256 last = slots[0];
        uint256 e = (last == NONE || t.timestamp <= last) ? 1 : t.timestamp - last;
        uint256 sd = wmul(SIGMA, sqrt(e * WAD) * 1e9);
        uint256 margin = wmul(pHat, K_SIG * sd);

        if (t.isBuy) {{
            // AMM bought X: fair >= gamma_bid * spot1, with equality if this was an arb
            uint256 pObs = wmul(spot1, WAD - bidF);
            bool arb = wmul(spot0, WAD - bidF) > pHat + margin;
            if (arb || pObs > pHat) pHat = pObs;
        }} else {{
            // AMM sold X: fair <= spot1 / gamma_ask, with equality if this was an arb
            uint256 pObs = wdiv(spot1, WAD - askF);
            bool arb = wdiv(spot0, WAD - askF) + margin < pHat;
            if (arb || pObs < pHat) pHat = pObs;
        }}

        // Fees linear in mispricing: raise the side an arb would hit, lower the other
        uint256 bid = BASE;
        uint256 ask = BASE;
        if (spot1 > pHat) {{
            uint256 s = wmul(wdiv(spot1 - pHat, pHat), THETA);
            bid = BASE + s;
            ask = BASE > s ? BASE - s : 0;
        }} else if (spot1 < pHat) {{
            uint256 s = wmul(wdiv(pHat - spot1, pHat), THETA);
            ask = BASE + s;
            bid = BASE > s ? BASE - s : 0;
        }}
        bid = clamp(bid, FLOOR, CAP);
        ask = clamp(ask, FLOOR, CAP);

        slots[0] = t.timestamp;
        slots[1] = pHat;
        slots[2] = spot1;
        slots[3] = bid;
        slots[4] = ask;
        return (bid, ask);
    }}

    function getName() external pure override returns (string memory) {{
        return "FairCenteredQuoting";
    }}
}}'''

best = 0
best_combo = None

for base in base_values:
    for theta in theta_values:
        code = template.format(base=base, theta=int(theta))
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
                best_combo = (base, theta)
            print(f"BASE={base} THETA={theta:.0e}: {edge:.2f} {status}")
        else:
            print(f"BASE={base} THETA={theta:.0e}: FAILED")
            if result.stderr:
                print(f"  {result.stderr[:200]}")

print(f"\nBest: BASE={best_combo[0]} THETA={best_combo[1]:.0e} = {best:.2f}")