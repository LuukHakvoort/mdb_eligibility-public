# Research Design and Methodology

*Draft for discussion. Placeholders marked [CHECK] need verification against your data.*

---

## 1. Sample construction: the eligible dyad-year panel

### 1.1 Unit of analysis

The unit of analysis is the **institution–country–year** (dyad-year). For each
multilateral development bank *i*, recipient country *j*, and year *t*, the
outcome is the total value of lending commitments approved by *i* to *j* in *t*,
expressed in millions of constant 2025 US dollars.

Aggregating project records to dyad-year totals serves two purposes. First, it
makes the zeros observable: a dyad-year in which a bank approved no lending is a
decision, and a project-level dataset cannot represent it. Second, it removes the
principal threat to cross-institutional comparability. Banks differ in what they
disclose as a "project" — some report tranches, sub-projects, and guarantees as
separate records, others bundle them — and because the finding of interest here
*is* the difference between institutions, granularity artefacts would be
indistinguishable from substantive divergence. Annual totals are comparable even
where project counts are not.

**[CHECK] Validation.** For each bank, compare the annual commitment totals
derived from the scraped data against the totals published in that bank's annual
report or financial statements. Report the correspondence in an appendix table.
Where the series diverge, document why (e.g. exclusion of technical assistance,
treatment of co-financing, calendar vs. fiscal year reporting).

### 1.2 The eligibility restriction

A naive panel would take the Cartesian product of 14 institutions × ~190
countries × 25 years. This would be wrong. The overwhelming majority of those
cells are not lending decisions at all: the Caribbean Development Bank cannot
lend to Mongolia, and IDA cannot lend to Germany. Including such cells as zeros
would generate the appearance of divergent allocation logics purely from
differences in institutional mandate — precisely the artefact that would
invalidate the heterarchy claim.

The panel is therefore restricted to **eligible dyad-years**. A dyad-year
(*i*, *j*, *t*) enters the estimation sample if and only if:

1. **Institutional existence.** Bank *i* was operational in year *t*.
2. **Membership.** Country *j* held membership (or recipient status, where these
   differ) in bank *i* during year *t*.
3. **Geographic mandate.** Country *j* fell within the geographic scope of *i*'s
   lending operations in year *t*.
4. **Window eligibility.** Where *i* is a concessional window, *j* met the
   relevant income and creditworthiness criteria in *t*.
5. **No structural bar.** Country *j* was not under suspension of lending,
   sanctions, or non-accrual status vis-à-vis *i* in year *t*.

All five conditions are **time-varying**. This matters more than it may appear:
the EBRD's countries of operations expanded from Central and Eastern Europe to
Central Asia, then to the Southern and Eastern Mediterranean, then to
sub-Saharan Africa; the EIB's core lending area changed with every EU
enlargement and with Brexit; the NDB added five members between 2021 and 2026.
A static eligibility rule would misclassify a substantial share of dyad-years.

### 1.3 Eligibility rules by institution

| Bank | Membership / recipient basis | Geographic scope | Window criteria | Key time variation |
|---|---|---|---|---|
| **IBRD** | Member states | Global | Above IDA cutoff; below graduation threshold; creditworthy | Annual per-capita income guidelines; graduations |
| **IDA** | Member states | Global | GNI p.c. below operational cutoff (USD 1,325 in FY26); plus Blend, Gap, and small-island exception countries | Annual eligibility list; graduations and reverse graduations |
| **AfDB** | Regional member countries (54) | Africa | ADB window: middle-income / creditworthy. ADF window: low-income | Country classification changes |
| **AsDB** | Developing member countries | Asia-Pacific | ADB window vs. ADF concessional | DMC graduations (e.g. Korea) |
| **IDB** | Borrowing member countries (26) | Latin America & Caribbean | — | Stable |
| **EBRD** | Countries of operations | Expanding: CEE → Central Asia → SEMED → sub-Saharan Africa & Iraq | Transition mandate | **Substantial**: mandate expanded repeatedly across the period |
| **EIB** | EU member states + external mandate regions | EU core; external lending mandate elsewhere | — | **Substantial**: 2004, 2007, 2013 enlargements; Brexit; successive external mandates |
| **IsDB** | Member countries (OIC members) | Member countries | ISFD for concessional | Accessions |
| **CAF** | Shareholder countries | Latin America & Caribbean (+ Iberian shareholders) | — | Membership expansion |
| **CDB** | Borrowing Member Countries | Caribbean | — | Largely stable |
| **AIIB** | Members (111 approved) | Members, regional and non-regional | In practice, developing members only | **Substantial**: 57 founding members (2016) → 111 |
| **BADEA** | Non-Arab African states | African Union members that are not Arab League members | — | Largely mechanical |
| **NDB** | Member countries | Members | — | **Substantial**: BRICS-5 (2015) + Bangladesh, UAE (2021), Egypt (2023), Algeria (2025), Uzbekistan (2026) |

**[CHECK] Three judgement calls to document explicitly:**

- **AIIB non-borrowing members.** Germany, the UK, and France are members but
  are not realistic borrowers. Either restrict AIIB eligibility to developing
  members using an income threshold, or retain all members and acknowledge that
  the resulting zeros are near-structural. State which, and show the results are
  robust to the alternative.
- **IBRD/IDA blend countries.** Blend countries are eligible for both. They
  should appear as eligible dyad-years for both institutions.
- **AfDB and AsDB window aggregation.** If your project data pools the
  non-concessional and concessional windows of these banks into a single
  institution, the resulting series mixes two lending logics. This is the most
  likely explanation for the multimodal commitment distributions you observe for
  the AfDB and IDB. Splitting the windows is preferable; if the data do not
  permit it, the limitation must be stated, since it directly affects the
  cross-institutional comparison.

### 1.4 Acknowledged limitation

Membership is not exogenous. States join MDBs partly in anticipation of
borrowing, and banks admit members strategically. Conditioning on eligibility
therefore conditions on a non-random variable. This is a limitation to
acknowledge rather than one that can be solved within this design. As a partial
check, the models can be re-estimated including a window of years prior to
accession, and the results compared.

---

## 2. Model specification

### 2.1 Why a hurdle model

Lending commitments in the eligible panel exhibit three features that rule out
log-linear OLS: a large mass at exactly zero, strong right skew among positive
values, and variance that scales with the mean. The first is the binding
constraint. Two families of models accommodate it:

- **Single-equation models with a log link** (Poisson, negative binomial, or
  PPML) generate zeros from the same process that generates positive values.
- **Hurdle models** treat participation and intensity as separate processes.

The hurdle specification is preferred here on substantive grounds. The decision
whether to engage with a country at all, and the decision how much to commit
once engaged, plausibly respond to different considerations. The first is a
gatekeeping decision made at board level and subject to political veto; the
second is constrained by project pipelines, absorptive capacity, country
allocation formulae, and capital adequacy. Collapsing them into one equation
assumes a single mechanism operates on both margins — an assumption this design
is well placed to test rather than impose.

The hurdle model is due to Cragg (1971), with the count-data variant developed
by Mullahy (1986); the closely related two-part model in health economics is
Duan et al. (1983).

### 2.2 Relationship to the Heckman selection model

The hurdle model is frequently confused with the Heckman (1979) selection model.
They differ in a way that matters for identification.

Heckman assumes the participation and outcome equations have **correlated
errors**: the same unobservables that determine whether lending occurs also
determine how much. Estimating that correlation requires an exclusion
restriction — a variable affecting participation but not intensity. Absent a
credible one, Heckman estimates are identified only off the nonlinearity of the
inverse Mills ratio and are known to be fragile (Leung and Yu 1996; Puhani 2000).

The hurdle model assumes the two processes are **conditionally independent given
the covariates**. Each equation is then a self-contained likelihood and is
identified on its own. **No exclusion restriction is required.** The trade-off is
that hurdle models cannot represent selection on unobservables: if there are
latent country characteristics that both attract lending and increase loan size,
the intensity equation is estimated on a non-random subsample and its
coefficients are conditional on selection.

For this application the hurdle assumption is defensible, because the eligibility
restriction already removes the most severe source of non-random selection
(structural ineligibility), and because the conditioning set is rich. The
assumption should nevertheless be stated explicitly and its implications for
interpretation acknowledged (see §3.4). Dow and Norton (2003) give the clearest
statement of when each model is appropriate; Madden (2008) compares their
performance empirically.

### 2.3 Notation

Let *i* = 1, …, 14 index institutions, *j* index recipient countries, and
*t* = 2002, …, 2026 index years. Let

- **y**<sub>*ijt*</sub> = total commitments from *i* to *j* in *t*, millions of constant 2025 USD
- **d**<sub>*ijt*</sub> = 1[y<sub>*ijt*</sub> > 0], the participation indicator
- **x**<sub>*ijt*</sub> = vector of *political* covariates, whose coefficients vary by institution
- **z**<sub>*ijt*</sub> = vector of *control* covariates, whose coefficients are pooled

with **x** containing the shareholder-weighted UNGA ideal point distance and the
neopatrimonial alignment term, and **z** containing the economic and political
controls. All continuous covariates are standardised (mean 0, SD 1) so that
priors are interpretable on a common scale and the varying-slope standard
deviations are comparable across variables.

### 2.4 Part 1 — the participation equation

d<sub>*ijt*</sub> ~ Bernoulli(π<sub>*ijt*</sub>)

logit(π<sub>*ijt*</sub>) = α<sup>π</sup><sub>*i*</sub> + γ<sup>π</sup><sub>*j*</sub> + δ<sup>π</sup><sub>*t*</sub> + **x**′<sub>*ijt*</sub> **β**<sup>π</sup><sub>*i*</sub> + **z**′<sub>*ijt*</sub> **θ**<sup>π</sup>

with institution-varying slopes drawn from a common distribution:

**β**<sup>π</sup><sub>*i*</sub> ~ MVNormal(**β̄**<sup>π</sup>, **Σ**<sup>π</sup>),  **Σ**<sup>π</sup> = diag(**τ**<sup>π</sup>) **Ω**<sup>π</sup> diag(**τ**<sup>π</sup>)

### 2.5 Part 2 — the intensity equation

Conditional on d<sub>*ijt*</sub> = 1:

y<sub>*ijt*</sub> ~ Lognormal(μ<sub>*ijt*</sub>, σ²)

log(μ<sub>*ijt*</sub>) = α<sup>μ</sup><sub>*i*</sub> + γ<sup>μ</sup><sub>*j*</sub> + δ<sup>μ</sup><sub>*t*</sub> + **x**′<sub>*ijt*</sub> **β**<sup>μ</sup><sub>*i*</sub> + **z**′<sub>*ijt*</sub> **θ**<sup>μ</sup>

**β**<sup>μ</sup><sub>*i*</sub> ~ MVNormal(**β̄**<sup>μ</sup>, **Σ**<sup>μ</sup>),  **Σ**<sup>μ</sup> = diag(**τ**<sup>μ</sup>) **Ω**<sup>μ</sup> diag(**τ**<sup>μ</sup>)

A Gamma likelihood with log link is a defensible alternative to the lognormal
and should be reported as a robustness check; the two differ in how they weight
the right tail, and commitment distributions are heavy-tailed. Compare via
approximate leave-one-out cross-validation (Vehtari, Gelman and Gabry 2017).

Note that **no rounding of the dependent variable is required**. This is an
advantage of the hurdle form over a Bayesian negative binomial, whose likelihood
is a probability mass function defined only on non-negative integers and would
require commitments to be discretised.

### 2.6 Priors

| Parameter | Prior | Rationale |
|---|---|---|
| **β̄**<sup>π</sup>, **β̄**<sup>μ</sup> | Normal(0, 1) | Weakly informative on standardised covariates |
| **θ**<sup>π</sup>, **θ**<sup>μ</sup> | Normal(0, 1) | As above |
| **τ**<sup>π</sup>, **τ**<sup>μ</sup> | Half-Normal(0, 1) | Regularises toward pooling; avoids boundary estimates at zero |
| **Ω**<sup>π</sup>, **Ω**<sup>μ</sup> | LKJ(2) | Mild shrinkage toward zero slope correlation (Lewandowski, Kurowicka and Joe 2009) |
| α<sub>*i*</sub>, γ<sub>*j*</sub>, δ<sub>*t*</sub> | Hierarchical, Normal(0, σ<sub>·</sub>) | Partial pooling of fixed effects |
| σ (lognormal scale) | Exponential(1) | |

Prior sensitivity should be assessed by re-estimating under Half-Normal(0, 0.5)
and Half-Normal(0, 2) for **τ**, since the posterior for a variance component
estimated from 14 groups carries non-trivial prior influence. Report this.

### 2.7 Estimation

Estimation in Stan via `brms` (Bürkner 2017; Carpenter et al. 2017), using a
non-centred parameterisation for the varying slopes to avoid the funnel geometry
that otherwise impedes sampling in hierarchical models. Convergence assessed by
R̂ < 1.01, effective sample size, and absence of divergent transitions
(Betancourt 2017). Four chains, [CHECK] iterations.

### 2.8 Why Bayesian estimation

Fourteen institutions is a small number of groups from which to estimate a
variance component. Frequentist mixed models in this regime frequently fail to
converge, return boundary estimates of exactly zero variance, or produce variance
estimates with no usable measure of uncertainty. Stegmueller (2013) documents
this directly, showing that Bayesian multilevel estimation substantially
outperforms maximum-likelihood alternatives when the number of higher-level units
is below roughly twenty; Gelman (2006) makes the corresponding case for
weakly informative priors on hierarchical variance parameters.

The argument is stronger still given that the quantity of interest here *is* the
variance component. Partial pooling also stabilises estimates for institutions
with short panels — the AIIB and NDB, operational only from 2016, contribute too
few dyad-years to support credible unpooled slopes but too much information to
discard. Shrinkage is the principled middle course, and it is an answer to the
obvious objection that little can be said about a bank founded in 2016.

A frequentist alternative would cluster standard errors at the institution level.
With fourteen clusters, cluster-robust inference is itself unreliable, since its
asymptotics assume a large number of clusters (Cameron and Miller 2015). The
frequentist repair is weakest precisely where the parameter of interest lies.

### 2.9 Robustness: pooled PPML with institution interactions

As a transparent frequentist check, estimate

y<sub>*ijt*</sub> = exp(α<sub>*i*</sub> + γ<sub>*j*</sub> + δ<sub>*t*</sub> + **x**′<sub>*ijt*</sub>**β** + Σ<sub>*i*</sub> **x**′<sub>*ijt*</sub>**β**<sub>*i*</sub>·1[bank = *i*] + **z**′<sub>*ijt*</sub>**θ**) · ε<sub>*ijt*</sub>

by Poisson pseudo-maximum-likelihood with standard errors clustered by
institution, and test the joint null that the interaction terms are zero. PPML is
consistent under correct specification of the conditional mean irrespective of
the true distribution (Gourieroux, Monfort and Trognon 1984; Santos Silva and
Tenreyro 2006) and accommodates high-dimensional fixed effects (Correia,
Guimarães and Zylkin 2020). It requires no distributional assumption, runs in
seconds, and delivers a single interpretable test — "are the political
coefficients equal across the fourteen banks?" — that complements the Bayesian
estimate of *how much* they differ.

---

## 3. Do the covariates differ across the two equations?

This is the question your specification most needs to answer explicitly, and the
answer has substantive consequences.

### 3.1 They need not differ, and here they should not

Because the hurdle model requires no exclusion restriction, the two equations may
contain **identical covariate vectors**. This specification is recommended here,
for three reasons.

**Identification is not at stake.** Any difference in covariates would be a
substantive assertion, not an identification necessity. Placing a variable in
the participation equation only asserts that it affects *whether* a bank lends
but has no effect on *how much* — a strong claim requiring theoretical
justification the literature does not currently supply.

**Interpretation depends on it.** If both equations contain the same covariates,
then any difference between **β**<sup>π</sup><sub>*i*</sub> and
**β**<sup>μ</sup><sub>*i*</sub> is substantive: it tells you that a variable
operates on one margin and not the other. If the specifications differ, that
comparison is confounded with the specification choice, and the most interesting
finding the model can produce becomes uninterpretable.

**Comparability across institutions.** The heterarchy claim rests on comparing
the same coefficient across fourteen banks. Bank-specific covariate sets would
destroy that comparison. The covariate vector must be constant across
institutions as well as across equations.

### 3.2 What the coefficients mean in each equation

Even with identical covariates, the two equations answer different questions:

| | Participation equation | Intensity equation |
|---|---|---|
| **Question** | Will bank *i* engage with country *j* at all this year? | Given engagement, how large is the commitment? |
| **Decision** | Board-level gatekeeping; country strategy; political veto | Pipeline capacity, country allocation formulae, absorptive capacity, capital adequacy |
| **Expected drivers** | Political alignment, regime affinity, strategic salience | Project scale, income, population, prior portfolio |
| **Interpretation of β** | Change in log-odds of any lending | Proportional change in commitment volume |

This maps directly onto the "dual technical and political pressures" you
identify in the introduction — and gives it empirical content. The plausible
hypothesis is that **political logics operate primarily on the extensive margin
while technical and formulaic logics dominate the intensive margin**. If borne
out, that is a more precise and more defensible claim than an undifferentiated
statement that politics shapes MDB lending.

### 3.3 Implications you must handle in interpretation

**Coefficients may take opposite signs across equations, and this is not a
contradiction.** GDP per capita is the clearest case: higher income raises
creditworthiness and therefore the probability of non-concessional lending
(positive in the participation equation), while conditional on lending, poorer
countries may receive larger concessional volumes (negative in the intensity
equation). Both are true simultaneously.

**No single coefficient gives the total effect.** The unconditional expectation
is the product of the two parts:

E[y<sub>*ijt*</sub> | **x**, **z**] = π<sub>*ijt*</sub> · E[y<sub>*ijt*</sub> | y<sub>*ijt*</sub> > 0, **x**, **z**]

Marginal effects on expected lending must therefore be computed from the full
posterior across both equations, not read off either coefficient table. Report
average marginal effects with credible intervals, computed by posterior
simulation.

**There are two variance components, not one.** The model yields
**τ**<sup>π</sup> and **τ**<sup>μ</sup> separately. This is a feature: it lets
you distinguish

- τ<sup>π</sup> large, τ<sup>μ</sup> small → banks differ in *whom they deal
  with* but not in how they size commitments. Heterarchy on the political
  gatekeeping margin.
- τ<sup>π</sup> small, τ<sup>μ</sup> large → banks agree on whom to engage but
  differ in how they allocate volume.
- Both large → divergent logics on both margins.
- Both near zero → a shared allocation logic; the World Bank-as-model assumption
  is vindicated.

The four cases have different implications for the external-validity claim, and
distinguishing them is a genuine contribution.

**Parameter count.** Two equations, two political variables, fourteen
institutions, plus controls and three sets of fixed effects. This is a large
model. Verify it samples adequately before committing to it, and be prepared to
report the participation equation as the primary analysis if the intensity
equation proves poorly identified in the banks with short panels.

### 3.4 The conditional-independence assumption

The intensity equation is estimated on the selected subsample of dyad-years with
positive lending. Under the hurdle assumption this is unproblematic, because
participation is assumed independent of the intensity error conditional on
covariates. If that assumption fails — if unobserved country attributes both
attract engagement and increase loan size — the intensity coefficients are
conditional on selection and should be described as such: they characterise
allocation *among engaged dyads*, not counterfactual allocation to all eligible
countries. State this in the limitations. It is a defensible position, but it
must be a stated one.

---

## 4. How the design answers the research question

The research question asks whether multilateral development banks allocate
lending according to the same organisational logic. The design gives that
question an explicit operational definition and a direct test.

**An organisational logic is a mapping from recipient characteristics to lending
decisions.** Two institutions share a logic if the same recipient attributes
predict their lending decisions with the same weights. In the notation above, a
logic is the vector **β**<sub>*i*</sub>, and two banks share a logic when
**β**<sub>*i*</sub> = **β**<sub>*i*′</sub>.

**The test is the posterior distribution of τ.** The varying-slope standard
deviations **τ**<sup>π</sup> and **τ**<sup>μ</sup> measure the dispersion of
institutional logics around the common mean:

- **τ concentrated near zero**: MDBs weight political characteristics
  identically. A common logic governs multilateral development finance, and
  findings from any one institution plausibly generalise to others.
- **τ substantially above zero**: MDBs weight the same characteristics
  differently. Allocation is governed by multiple competing logics rather than
  one — the empirical signature of heterarchy — and the assumption that
  World Bank findings extend to other MDBs does not hold.

Report the full posterior for τ, not a point estimate, together with the
shrunken institution-specific slopes **β**<sub>*i*</sub>. Supplement with a
formal comparison of the varying-slope model against a common-slope restriction
via approximate leave-one-out cross-validation (Vehtari, Gelman and Gabry 2017).

**Substantive magnitude.** Because τ is on a standardised log-odds or log-volume
scale, translate it into something interpretable: simulate from the posterior the
predicted lending each bank would extend to an identical hypothetical recipient,
and report the spread across institutions. A statement of the form "holding
recipient characteristics constant, predicted commitments differ by a factor of
*X* across institutions" communicates the finding far better than a variance
parameter.

**A null result is still a result.** If the logics converge, the paper has tested
and validated an assumption on which a large body of single-institution research
implicitly depends. If they diverge, it has shown that this literature has a
generalisability problem. The contribution does not depend on which way the
result falls — a point worth stating in the introduction.

**On neo-royalism.** Within this design, the neo-royalist hypothesis is not a
separate framework but one varying slope among others: the coefficient on
neopatrimonial alignment, **β**<sup>neopat</sup><sub>*i*</sub>, and its
dispersion across institutions. This keeps the empirical architecture unified
while still allowing the question to be asked. Treating it as a second headline
contribution requiring its own measure, its own theory section, and its own
defence is what makes the introduction hard to follow.

---

## 5. References

### Model and estimation

- Betancourt, Michael. 2017. "A Conceptual Introduction to Hamiltonian Monte Carlo." arXiv:1701.02434.
- Bürkner, Paul-Christian. 2017. "brms: An R Package for Bayesian Multilevel Models Using Stan." *Journal of Statistical Software* 80 (1): 1–28.
- Cameron, A. Colin, and Douglas L. Miller. 2015. "A Practitioner's Guide to Cluster-Robust Inference." *Journal of Human Resources* 50 (2): 317–72.
- Carpenter, Bob, et al. 2017. "Stan: A Probabilistic Programming Language." *Journal of Statistical Software* 76 (1): 1–32.
- Correia, Sergio, Paulo Guimarães, and Tom Zylkin. 2020. "Fast Poisson Estimation with High-Dimensional Fixed Effects." *Stata Journal* 20 (1): 95–115.
- Cragg, John G. 1971. "Some Statistical Models for Limited Dependent Variables with Application to the Demand for Durable Goods." *Econometrica* 39 (5): 829–44.
- Dow, William H., and Edward C. Norton. 2003. "Choosing Between and Interpreting the Heckit and Two-Part Models for Corner Solutions." *Health Services and Outcomes Research Methodology* 4 (1): 5–18.
- Duan, Naihua, Willard G. Manning, Carl N. Morris, and Joseph P. Newhouse. 1983. "A Comparison of Alternative Models for the Demand for Medical Care." *Journal of Business & Economic Statistics* 1 (2): 115–26.
- Gelman, Andrew. 2006. "Prior Distributions for Variance Parameters in Hierarchical Models." *Bayesian Analysis* 1 (3): 515–34.
- Gelman, Andrew, and Jennifer Hill. 2007. *Data Analysis Using Regression and Multilevel/Hierarchical Models*. Cambridge: Cambridge University Press.
- Gelman, Andrew, John B. Carlin, Hal S. Stern, David B. Dunson, Aki Vehtari, and Donald B. Rubin. 2013. *Bayesian Data Analysis*. 3rd ed. Boca Raton: CRC Press.
- Gourieroux, Christian, Alain Monfort, and Alain Trognon. 1984. "Pseudo Maximum Likelihood Methods: Applications to Poisson Models." *Econometrica* 52 (3): 701–20.
- Heckman, James J. 1979. "Sample Selection Bias as a Specification Error." *Econometrica* 47 (1): 153–61.
- Leung, Siu Fai, and Shihti Yu. 1996. "On the Choice Between Sample Selection and Two-Part Models." *Journal of Econometrics* 72 (1–2): 197–229.
- Lewandowski, Daniel, Dorota Kurowicka, and Harry Joe. 2009. "Generating Random Correlation Matrices Based on Vines and Extended Onion Method." *Journal of Multivariate Analysis* 100 (9): 1989–2001.
- Madden, David. 2008. "Sample Selection Versus Two-Part Models Revisited: The Case of Female Smoking and Drinking." *Journal of Health Economics* 27 (2): 300–307.
- McElreath, Richard. 2020. *Statistical Rethinking: A Bayesian Course with Examples in R and Stan*. 2nd ed. Boca Raton: CRC Press.
- Mullahy, John. 1986. "Specification and Testing of Some Modified Count Data Models." *Journal of Econometrics* 33 (3): 341–65.
- Puhani, Patrick A. 2000. "The Heckman Correction for Sample Selection and Its Critique." *Journal of Economic Surveys* 14 (1): 53–68.
- Santos Silva, J. M. C., and Silvana Tenreyro. 2006. "The Log of Gravity." *Review of Economics and Statistics* 88 (4): 641–58.
- Stegmueller, Daniel. 2013. "How Many Countries for Multilevel Modeling? A Comparison of Frequentist and Bayesian Approaches." *American Journal of Political Science* 57 (3): 748–61.
- Vehtari, Aki, Andrew Gelman, and Jonah Gabry. 2017. "Practical Bayesian Model Evaluation Using Leave-One-Out Cross-Validation and WAIC." *Statistics and Computing* 27 (5): 1413–32.

### Measures

- Bailey, Michael A., Anton Strezhnev, and Erik Voeten. 2017. "Estimating Dynamic State Preferences from United Nations Voting Data." *Journal of Conflict Resolution* 61 (2): 430–56.
- Coppedge, Michael, et al. [year]. "V-Dem [Country-Year] Dataset v[XX]." Varieties of Democracy Project. *[CHECK version used]*
- Pemstein, Daniel, et al. 2025. "The V-Dem Measurement Model: Latent Variable Analysis for Cross-National and Cross-Temporal Expert-Coded Data." V-Dem Working Paper 21.
- Sigman, Rachel, and Staffan I. Lindberg. 2017. "Neopatrimonialism and Democracy: An Empirical Investigation of Africa's Political Regimes." V-Dem Working Paper 56. University of Gothenburg.
- Sigman, Rachel, and Staffan I. Lindberg. 2019. "Neopatrimonialism and Democracy." In *The Routledge Handbook of Democratization in Africa*, edited by Gabrielle Lynch and Peter VonDoepp. London: Routledge.

### Substantive literature

- Bratton, Michael, and Nicolas van de Walle. 1997. *Democratic Experiments in Africa*. Cambridge: Cambridge University Press.
- Bull, Hedley. 1995 [1977]. *The Anarchical Society*. 2nd ed. London: Macmillan.
- Bunte, Jonas B. 2019. *Raise the Debt: How Developing Countries Choose Their Creditors*. Oxford: Oxford University Press.
- Dreher, Axel, Jan-Egbert Sturm, and James Raymond Vreeland. 2009. "Development Aid and International Politics: Does Membership on the UN Security Council Influence World Bank Decisions?" *Journal of Development Economics* 88 (1): 1–18.
- Goddard, Stacie E., and Abraham Newman. 2025. "Further Back to the Future: Neo-Royalism, the Trump Administration, and the Emerging International System." *International Organization* 79 (S1): S12–S25.
- Heldt, Eugénia C., and Henning Schmidtke. 2019. "Explaining Coherence in International Regime Complexes." *Review of International Political Economy* 26 (6): 1160–86.
- Humphrey, Chris. 2016. "The Invisible Hand: Financial Pressures and Organisational Convergence in Multilateral Development Banks." *Journal of Development Studies* 52 (1): 92–112.
- Kilby, Christopher. 2009. "The Political Economy of Conditionality: An Empirical Analysis of World Bank Loan Disbursements." *Journal of Development Economics* 89 (1): 51–61.
- Leeds, Brett Ashley, Layna Mosley, B. Peter Rosendorff, and Ayşe Zarakol. 2025. "The Future of Global Governance and World Order." *International Organization* 79 (S1): S1–S11.
- Zeitz, Alexandra O. 2021. "Emulate or Differentiate? Chinese Development Finance, Competition, and World Bank Infrastructure Funding." *Review of International Organizations* 16 (2): 265–92.

*[CHECK] Verify all page numbers and volume details against the originals before submission.*
