# Method, numerical implementation and limits

This is an independent collaboration proposal, not a UTOPYS system or validation. The runnable model is deliberately scalar; it is a scientific teaching and discussion tool, not operational dispatch software.

## 1. Units and sign conventions

Let `P` be available renewable power (MW), `s = Ps` scheduled power (MW), `M = Pmax` capacity (MW), `Δt` the interval duration (h), and `c_o, c_u ≥ 0` penalties (€/MWh):

```text
ℓ(s,p) = Δt [c_o (s − p)_+ + c_u (p − s)_+].
```

When `s > p`, available generation was **overestimated** and there is a shortfall; `c_o` applies. When `s < p`, it was **underestimated** and there is a surplus; `c_u` applies. The penalties are illustrative and might stand for imbalance, reserve, curtailment or opportunity cost only when justified by the actual settlement design. Avoid double counting other objective terms. Loss and expectation are in **euros per interval**.

For a discrete reference `P̂₀ = Σ wᵢ δ_{pᵢ}`, `wᵢ > 0` and `Σwᵢ=1`, the implemented nominal UCF is the exact finite sum:

```text
U₀(s) = Σᵢ wᵢ ℓ(s,pᵢ)
      = Δt c_o Σᵢ wᵢ(s−pᵢ)_+ + Δt c_u Σᵢ wᵢ(pᵢ−s)_+.
```

For a continuous density this corresponds to the two usual integrals over `[0,s]` and `[s,M]`; for atoms, an expectation or Stieltjes integral is appropriate. The plot aggregates probability and cost into bins; it does not assume empirical data have a density. Bar heights are mass or expected cost per bin width, so rectangular area recovers the sum.

The objective is convex. For positive `c_o,c_u`, one minimum is a generalised quantile at level `c_u/(c_o+c_u)`. With an atom at `s`, its left and right derivatives can differ; the app displays the interval

```text
∂U₀(s) = Δt [(c_o+c_u) F₀(s−) − c_u,
              (c_o+c_u) F₀(s)  − c_u].
```

If `c_u=0`, the implementation returns the valid minimiser 0; if `c_o=0`, it returns M; if both are zero, all schedules are minima. These are minima of the **standalone UCF**, not of an OPF, multi-period dispatch or constrained power system.

### Continuous beta: analytical expression

For `P=MZ`, `Z~Beta(α,β)`, `μ=α/(α+β)`, `z=s/M` and regularised incomplete beta `I_z`, the animation compares Monte Carlo with the closed-form continuous-beta expectation:

```text
E[(s−P)_+] = s I_z(α,β) − M μ I_z(α+1,β)
E[(P−s)_+] = M μ [1−I_z(α+1,β)] − s [1−I_z(α,β)]
U(s) = Δt[c_o E[(s−P)_+] + c_u E[(P−s)_+]].
```

The special functions are evaluated numerically using SciPy. This is an analytical expression for the chosen continuous beta model, not proof that a beta law describes field data. For uploaded CSVs, the corresponding exact model expectation is the finite weighted sum above.

## 1b. Illustrative firming: renewable resource plus backup

The visible `Ps` controls on pages 02 and 03 are linked to the sidebar. A separate scenario slider changes one realised renewable output `p`; it does **not** change the distribution used for expectations. The settings are synthetic and adjustable.

For a battery with usable capacity `E_max` (MWh), initial state of charge `z ∈ [0,1]`, AC discharge and charge limits `P_dis` and `P_ch` (MW), and one-way efficiencies `η_dis, η_ch ∈ (0,1]`, the interval-wide available powers are

```text
D = min(P_dis, E_max z η_dis / Δt)
C = min(P_ch, E_max (1−z) / (η_ch Δt)).
```

For `s = Ps` and any realised `p`, an ideal fixed rule delivers up to `D` to cover a deficit and charges up to `C` to absorb a surplus:

```text
d(p) = min((s−p)_+, D)             # discharge, MW
q(p) = min((p−s)_+, C)             # charge, MW
g(p) = p + d(p) − q(p)             # net output delivered to the system, MW
E_final = E_max z + η_ch q(p) Δt − d(p) Δt / η_dis.
```

Because a point cannot simultaneously have a shortfall and a surplus, `d·q=0`. For dispatchable backup, `D=min(P_reserve, E_available/Δt)` and `C=0`; there is no charging. With no backup both limits are zero. The fixed policy observes `p` and reacts immediately; it acts even when operation is more expensive than the imbalance penalty. It is **not** an economic or stochastic optimiser.

The residual penalty and total cost for one scenario are

```text
ℓ_B(s,p) = Δt [c_o(s−p−D)_+ + c_u(p−s−C)_+ + c_B(d(p)+q(p))].
U_B(s) = E[ℓ_B(s,P)] = expected residual penalty + expected backup operation cost.
```

`c_B` is a single illustrative charge or discharge operating cost per MWh of AC-side throughput, applied to both `d` and `q`. It is not a complete cost of storage: investment, lost opportunity, degradation beyond this simple coefficient, emissions and other system costs are omitted. Residual surplus is penalised as specified; alternative curtailment or market arrangements are not modelled. Thus `U_B` may be above or below the unbacked cost, and the unbacked UCF minimum is not a joint-system optimum.

Expected residual distances follow from the same beta or empirical positive-part expressions:

```text
R₋ = E[(s−D−P)_+]     R₊ = E[(P−s−C)_+]
E[d] = E[(s−P)_+]−R₋   E[q] = E[(P−s)_+]−R₊.
```

For an empirical distribution, probabilities include atoms on the coverage boundaries. Specifically, `Pr(no residual shortfall)=Pr(P≥s−D)` includes scenarios with no initial shortfall, while `Pr(exact match)=Pr(s−D≤P≤s+C)` also requires surplus to be fully absorbed. These are probabilities **under the selected one-interval distribution and fixed initial energy**, not independently validated reliability estimates.

Let `ν_B = Law(g(P))` be the post-backup net-output distribution for the current `s` and initial state. Then

```text
W₁(ν_B,δ_s)=R₋+R₊                                      [MW]
expected residual penalty=Δt(c_o R₋+c_u R₊)           [€/interval]
U_B(s)=expected residual penalty + Δt c_B(E[d]+E[q]).
```

The app transports both the raw and post-backup distributions to `δ_s`; it separately displays backup operation cost. As before, metric `W₁` is not a cost. The post-backup quantile markers are obtained by applying `g` to the raw quantiles; `g` is nondecreasing. The post-backup distances are checked via independent CDF integrals at the thresholds `s−D` and `s+C` (clipped to the physical support).

**Scope:** Each realised renewable and backup power is assumed constant over `Δt`, and each possible outcome starts from the **same** initial SOC or reserve-energy budget. There is no intra-interval fluctuation, sequence of intervals, replenishment strategy, ramping, response delay, forecast/information error, availability failure, network/inverter constraint or detailed degradation model. This is a sensitivity illustration of scenario-by-scenario controllability, not a real-time controller or guarantee of firm supply, reliability, safety or stability. The displayed two-distribution sensitivity and DRO section remain the original **unbacked** loss `ℓ`; selecting backup does not change that DRO calculation.

## 2. Reference and comparison distributions

- **Synthetic beta:** a beta density with nominal shape parameters `α = μκ`, `β = (1−μ)κ`, where `μ` is the target fraction of capacity and `κ` is concentration. For the existing cost curves, reference/comparison W₁ and DRO, the code samples its unnormalised density at **200 midpoints** and normalises the weights. This is a discrete approximation, not an exact continuous beta law; its computed mean may differ from the target, especially near boundaries. The analytic/Monte Carlo backup comparison and raw/post-backup Dirac comparisons use the continuous beta instead, so their values may differ slightly from the discrete plots.
- **CSV:** each row is a finite scenario in `[0,M]`; positive weights are optional and normalised separately in the two groups. Repeated powers are combined. Both reference and comparison are required. The comparison may be an alternative or held-out sample only if the user designed it accordingly; merely labelling it `comparison` does not prove independence.
- **Monte Carlo animation:** for synthetic beta, draws are taken directly from the same continuous beta used in the closed form; for a CSV, draws resample the weighted empirical reference measure. Both analytic and Monte Carlo paths apply the same selected fixed backup rule and operating cost. The nested checkpoints use seed 42. The displayed `±1.96 standard errors` is an approximate *pointwise* interval, not a simultaneous convergence guarantee; it assesses sampling variability conditional on the selected model, not model misspecification or physical uncertainty. The 200-midpoint UCF/DRO plots remain a separate discrete approximation.

## 3. W₁ and sensitivity

For the two one-dimensional probability measures on the common bounded support:

```text
W₁(F₀,F₁) = ∫₀ᴹ |F₀(p)−F₁(p)| dp  (MW).
```

The software integrates the step CDFs exactly for the given discrete measures (up to floating-point arithmetic); it does not estimate W₁ from the 17 animated quantile markers. For this particular loss, `L = Δt max(c_o,c_u)` has units €/MW per interval and

```text
|E₁ℓ(s,P) − E₀ℓ(s,P)| ≤ L W₁(F₀,F₁).
```

It is an upper bound, not an equality, not a statement that the comparison is worst-case, and not a stability certificate. The comparison is inside the ambiguity ball only when `W₁ ≤ ε`.

### Scheduled power as a Dirac delta

For fixed schedule `s` model the scheduled distribution as the Dirac measure `δ_s`. The unique coupling sends each `p` to `s`, so

```text
W₁(μ,δ_s) = E_μ|P−s| = W₋ + W₊                           [MW]
W₋ = E[(s−P)_+] = ∫₀ˢ F(p) dp                             [MW]
W₊ = E[(P−s)_+] = ∫ₛᴹ [1−F(p)] dp                         [MW]
U(s) = Δt [c_o W₋ + c_u W₊]                               [€/interval].
```

Thus the loss is a *direction-weighted transport cost* for the unique coupling to `δ_s`. When `c_o=c_u=c`, it simplifies exactly to `U(s)=Δt·c·W₁(μ,δ_s)`. If penalties differ, the raw W₁ value alone does not determine the cost without directional information; it is in MW and cannot be compared directly with euros. An asymmetric weighted transport cost is **not** the usual symmetric metric W₁.

For a beta reference, the app independently integrates the CDF with adaptive quadrature on either side of `s` and compares the result with the closed-form beta UCF. For a CSV, it computes W₁ exactly for the finite measure and obtains the directional components from W₁ and `E[P]−s`. The 17 animated quantile particles illustrate movement; the displayed distance and cost use the full model, not those 17 markers. During animation, mass is interpolated towards `s`, so accumulated distance/cost scales linearly with visual progress `t`. This `t` is not the DRO radius.

## 4. Distributionally robust UCF — without backup

This DRO section uses the original loss `ℓ`, not the backed loss `ℓ_B`; the backup selector does not alter it. The model permits **any probability measure on the continuous support** `[0,M]` within W₁ distance `ε` of the discrete reference:

```text
U_DRO(s) = sup{ E_Q ℓ(s,P) : W₁(Q,P̂₀) ≤ ε, supp(Q) ⊆ [0,M] }.
```

For the scalar piecewise-linear loss above, its dual reduces to

```text
min_{λ≥0} { λε + Σᵢ wᵢ max[
    ℓ(s,pᵢ), Δt c_o s − λpᵢ,
    Δt c_u(M−s) − λ(M−pᵢ)
] }.
```

For each reference atom, the inner maximisation over candidate `p∈[0,M]` is attained at `p=0`, `p=pᵢ`, or `p=M`: the objective is convex on both sides of `pᵢ`. Because the loss is `L`-Lipschitz, a dual minimiser can be found in `[0,L]` for `ε>0`; the app bisects a convex subgradient for 38 iterations. At `ε=0`, it returns the nominal UCF. At fixed `s`, enlarging ε cannot decrease the worst-case value; `U_DRO(s) ≤ U₀(s)+Lε`. Bounded support can make this ceiling loose.

The robust optimum shown is the minimum over **201 equally spaced schedules** plus the current schedule, the reference mean and (when defined) a nominal optimum. The base spacing is `M/200`; it is a grid approximation, not necessarily the continuous optimum. The app reports the worst value, not a recovered adversarial distribution. Radii are illustrative and have no inherent statistical coverage.

## 5. Verification included

`tests/test_ucf_core.py` tests default values, units via decomposition, W₁ for weighted/duplicate atoms, quantiles and atom subgradients, zero penalties, bin areas, valid/invalid CSV, zero radius, monotonicity, bounded-support limits and the Lipschitz ceiling. A separately formulated **primal transport linear program** (`scipy.optimize.linprog`) is compared against the scalar dual for 40 seeded random distributions at four radii (160 cases), plus 18 one-penalty-zero cases. The primal includes the candidate endpoints and reference atoms; it does not reuse the dual solver. `tests/test_analytic_ucf.py` compares the closed-form beta cost with independent PDF quadrature and the Dirac-CDF integration, including unequal, equal and zero penalties, endpoints and empirical atoms. `tests/test_firming.py` checks battery/reserve energy and power limits, final SOC, weighted empirical boundary atoms, unbacked equivalence, post-backup transport, beta PDF quadrature, Monte Carlo and the fact that a costly fixed rule can increase total cost. `tests/test_app.py` checks the three-page order, bidirectional Ps synchronisation, bilingual navigation, backup modes, capacity clamping, zero cases and no-upload path; `tests/test_animations.py` checks animation data. These tests do not validate real-world assumptions, facility access, EMT models or scientific efficacy.

## 6. Proposed extension toward UTOPYS

Start with an agreed network, data governance, settlement rules and feasible policies. Preserve spatial/temporal dependence and topology; for multivariate Wasserstein distance specify a physically scaled ground metric. Infer uncertain parameters using PMU data only where identifiable, with higher-bandwidth observations and/or engineering priors for fast converter dynamics if necessary. Separate measurement noise from model discrepancy.

Calibrate candidate ambiguity radii using held-out periods, dependence-aware block resampling or cross-validation, and report assumptions before any statistical coverage claim. Compare mean/forecast, nominal-UCF and DRO policies with identical network constraints, information, time horizons and matched scenarios. Measure out-of-sample cost, tail/CVaR and physical indicators, plus computational effort and surrogate error. Discontinuous failure events require their own statistical and rare-event treatment: the above scalar Lipschitz inequality cannot automatically bound their probabilities.

Dynamic or EMT comparison is a proposed later research activity, subject to suitable models and agreed access. UTOPYS’s public facility page says commissioning is under way, present access is limited to consortium partners and independent external applications are expected in 2029; verify the current rules and availability before relying on them.
