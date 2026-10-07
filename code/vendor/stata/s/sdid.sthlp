{smcl}
{* *! version 2.0.0 January, 2024}
{cmd:help sdid}{right: ({browse "https://doi.org/10.1177/1536867X241297914":SJ24-4: st0757})}
{hline}

{title:Title}

{p2colset 5 13 15 2}{...}
{p2col :{cmd:sdid} {hline 2}}Synthetic difference-in-differences estimation, inference, and visualization


{marker syntax}{...}
{title:Syntax}

{p 8 12 2}
{cmd:sdid} {it:depvar} {it:groupvar} {it:timevar} {it:treatment} {ifin}{cmd:,}
{opt vce(vcetype)} [{it:options}]

{synoptset 29 tabbed}{...}
{synopthdr}
{synoptline}
{p2coldent:* {opt vce(vcetype)}}{it:vcetype} must be {opt bootstrap}, {cmd:jackknife}, {opt placebo}, or {opt noinference}{p_end}
{synopt :{cmd:covariates(}{it:{help varlist:varlist}}[{cmd:,} {it:type}]{cmd:)}}allow for the inclusion of covariates in the calculation
of the synthetic counterfactual; optional {it:type} can be specified as either {cmd:optimized} (the default) or {cmd:projected}, which is preferable in certain circumstances{p_end}
{synopt :{opt seed(#)}}set random-number seed to {it:#}{p_end}
{synopt :{opt reps(#)}}repetition for bootstrap and placebo inference{p_end}
{synopt :{opt method(type)}}allow for an estimation method to be requested;
{it:type} can be {cmd:sdid} (which is estimated by default), {cmd:did} (for
standard difference in differences), or {cmd:sc} (for standard synthetic control){p_end}
{synopt :{opt zeta_lambda(#)}}allow for control of the regularization parameter (zeta) defined in 
 {help sdid##Arkhangelsky21:Arkhangelsky et al. [2021, (5)]}; default values
 described in {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)} are used{p_end}
{synopt :{opt zeta_omega(#)}}allow for control of the regularization parameter (zeta) defined in 
 {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}; default values
 described in  {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)} are used{p_end}
{synopt :{opt min_dec(#)}}estimation of optimal weights occurs iteratively
until a sequential stopping rule is met; by default, a minimum is assumed when
consecutive iterations move by no more than the value specified in
{cmd:min_dec()}{p_end}
{synopt :{opt max_iter(#)}}define the maximum number of iterations to be
performed when calculating optimal weights; by default, a maximum of 10,000 iterations will be performed{p_end}
{synopt :{opt level(#)}}specify the confidence level, as a percentage, for
confidence intervals; default is the level set by {cmd:set level} (which, by
default, is {cmd:level(95)}){p_end}
{synopt :{opt graph}}specify that graphs be displayed in the style of figure 1
from {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}{p_end}
{synopt :{opt g1on}}if graphing is requested, activate the unit-specific weight graph{p_end}
{synopt :{cmd:g1_opt(}{it:{help twoway_options:graph_options}}{cmd:)}}modify the appearance of the unit-specific weight graph{p_end}
{synopt :{cmd:g2_opt(}{it:{help twoway_options:graph_options}}{cmd:)}}modify the appearance of the outcome trend graphs{p_end}
{synopt :{cmd:graph_export(}[{it:stub}]{cmd:,} {it:{help graph export:type}}{cmd:)}}allow for generated graphs to be saved to the disk{p_end}
{synopt :{opt msize(markersizestyle)}}modify the size of the marker for graph 1{p_end}
{synopt :{opt unstandardized}}in the case of {cmd:optimized} covariates, they will be standardized as {it:z} scores
unless this option is specified{p_end}
{synopt :{opt mattitles}}request that weights returned in matrices be accompanied by the name
of the {it:groupvar} corresponding to each weight{p_end}
{synopt :{opt verbose}}request additional output, such as warning messages
if the number of iterations specified in {cmd:max_iter()} is reached{p_end}
{synopt :{opt returnweights}}indicate that estimated weights omega and lambda should be returned directly in the dataset corresponding to each unit{p_end}
{synopt :{opt generate(string)}}specify that the variables containing omega
and lambda weights returned if the {cmd:returnweights} option is specified should be named starting with the specified {it:string}{p_end}
{synoptline}
{p2colreset}{...}
{p 4 6 2}
* {opt vce()} is required.


{marker description}{...}
{title:Description}

{pstd}
{cmd:sdid} implements the synthetic difference-in-differences (SDID)
estimation procedure along with several inference and graphing procedures as
described in {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}.  SDID is
based on a panel (group by time) setup, in which certain units are treated and
remaining units are untreated.  The {cmd:sdid} procedure calculates a
treatment effect as the pre- versus post-difference in differences between
treated units and synthetic control units, where synthetic control units are
chosen as an optimally weighted function of untreated units (unit-specific
weights) and pretreatment times (time-specific weights).  The {cmd:sdid}
command implements the procedures described in
{help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}.  The exact estimation
procedure implemented by {cmd:sdid} is described in their algorithm 1.
Further discussion of this procedure and its implementation in Stata is
available in {help sdid##Clarke23:Clarke et al. (2023)}.

{pstd}
Much of {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)} focuses on
cases with a single time period of adoption.  However, their appendix A lays
out the estimation procedure in cases of staggered adoption designs, where
treated units can adopt treatment at different moments of time while control
units never adopt.  {cmd:sdid} seamlessly estimates treatment effects in cases
with both single-time periods of treatment and multiple-time periods of
treatment.  In the latter case, rather than calculating a single unit- and
time-specific weight vector, an optimal unit- and time-specific weight vector
is calculated for each adoption period.  The reported average treatment effect
on the treated (ATT) in the staggered adoption design is the weighted estimand
described in {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021, app. A)}.
Additionally, adoption-period-specific estimates and their standard errors are
returned after estimation.

{pstd}
Inference in {cmd:sdid} is based on a bootstrap, jackknife, or placebo
procedure.  Each procedure is clustered by {it:groupvar} and follows the
precise algorithms laid out in
{help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}.  Specifically,
bootstrap inference follows algorithm 2, jackknife inference follows algorithm
3, and placebo inference follows algorithm 4.  The suitability of each
inference procedure depends on the precise data structure.  For example,
bootstrap and jackknife procedures are not appropriate with single treated
units, while placebo inference requires at least one more control than treated
unit.  Inference procedures are provided as standard for both single-treatment
and staggered adoption designs.  In the case of staggered adoption designs,
resample inference is conducted over the entire ATT and so provides a valid
standard error for the headline treatment effect (under the large sample
conditions laid out in
{help sdid##Arkhangelsky21:Arkhangelsky et al. [2021]}).  In very large
databases, bootstrap procedures may be computationally expensive, in which
case the jackknife will be a more (computationally) feasible inference
procedure.

{pstd}
{cmd:sdid} additionally allows for the inclusion of covariates in several ways
and, if requested, provides graphical output documenting optimal weights, as
well as matched treatment and synthetic control trends underlying the SDID
framework.  Details related to covariates and graphical options are described
at more length below.


{marker options}{...}
{title:Options}

{phang}
{opt vce(vcetype)} is required.  {it:vcetype} must be one of {cmd:bootstrap},
{cmd:jackknife}, {cmd:placebo}, or {cmd:noinference}, where in each case,
inference proceeds following the specified method.  For {cmd:bootstrap}, this
is permitted only if more than one unit is treated.  For {cmd:jackknife}, this
is permitted only if more than one unit is treated in each treatment period
(if multiple treatment periods are considered).  For {cmd:placebo}, this
requires at least one more control than treated unit to allow for permutations
to be constructed.  In each case, inference follows the specific algorithm
laid out in {help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}.  We allow
the {cmd:noinference} option should one wish to simply generate the point
estimator.  This is useful if you wish to plot outcome trends without the
added computational time associated with inference procedures.

{phang}
{cmd:covariates(}{it:{help varlist:varlist}}[{cmd:,} {it:type}]{cmd:)}
specifies that covariates should be included as a {it:varlist}.  If it is
specified, treatment and control units will be adjusted based on covariates in
the SDID procedure.  Optionally, {it:type} may be specified, which indicates
how covariate adjustment will occur.  If {it:type} is specified as
{cmd:optimized} (the default), this will follow the method described in
{help sdid##Arkhangelsky21:Arkhangelsky et al. (2021, n. 4)}, where SDID is
applied to the residuals of all units after regression adjustment.  However,
this has been observed to be problematic at times (refer to
{help sdid##Kranz22:Kranz [2022]}) and is also sensitive to optimization if
covariates have high dispersion.  Thus, an alternative type is implemented
({cmd:projected}), which consists of conducting regression adjustment based on
parameters estimated only in untreated units.  This type follows the procedure
proposed by {help sdid##Kranz22:Kranz (2022)} ({cmd:xsynth} in R) and is
observed to be more stable in some implementations (and at times, considerably
faster).  {cmd:sdid} will run simple checks on the covariates indicated and
return an error if covariates are constant to avoid multicollinearity.
However, before you run {cmd:sdid}, you are encouraged to ensure that
covariates are not perfectly multicollinear with other covariates and state-
and year-fixed effects in a simple two-way fixed-effects regression.  If
perfectly multicollinear covariates are included, {cmd:sdid} will execute
without errors.  However, where {it:type} is {cmd:optimized}, the procedure
may be sensitive to the inclusion of redundant covariates.

{phang}
{opt seed(#)} defines the seed for pseudo-random numbers.

{phang}
{opt reps(#)} sets the number of repetitions used in the calculation of
bootstrap and placebo standard errors.  The default is {cmd:reps(50)}.  Larger
values should be preferred where possible.

{phang}
{opt method(type)} allows you to change the estimation method.  {it:type} must
be one of {cmd:sdid}, {cmd:sc}, or {cmd:did}, where {cmd:sdid} refers to SDID,
{cmd:sc} refers to synthetic control, and {cmd:did} refers to difference in
differences.  The default is {cmd:method(sdid)}.

{phang}
{opt zeta_lambda(#)} specifies the value used when defining the regularization
term for time weight calculations.  This value is the scalar prior to the
sigma term used to calculate zeta.  The default is {cmd:zeta_lambda(1e-6)}.
This is relevant only when {cmd:method(sdid)} is used; otherwise, time weights
are not used.

{phang}
{opt zeta_omega(#)} specifies the value used when defining the regularization
term for unit weight calculations.  This value is the quantity prior to the
sigma hat term used to calculate zeta defined in
{help sdid##Arkhangelsky21:Arkhangelsky et al. [2021, (5)]}).  The default is
(N_tr*T_post)^1/4.  For other methods, the default value is
{cmd:zeta_omega(1e-6)}.

{phang}
{opt min_dec(#)} specifies that the estimation of optimal weights occurs
iteratively until a sequential stopping rule is met.  By default, a minimum is
assumed when consecutive iterations move by no more than the value specified
in {cmd:min_dec()}.  The default is {cmd:min_dec(1e-5)}.

{phang}
{opt max_iter(#)} defines the maximum number of iterations to be performed
when calculating optimal weights.  By default, a maximum of 10,000 iterations
will be performed.  Larger values can be set to ensure that a minimum is
reached.

{phang}
{opt level(#)} specifies the confidence level, as a percentage, for confidence
intervals.  The default is the level set by {cmd:set level} (which, by
default, is {cmd:level(95)}).

{phang}
{opt graph} specifies that graphs will be displayed showing unit and time
weights as well as outcome trends as per figure 1 from
{help sdid##Arkhangelsky21:Arkhangelsky et al. (2021)}.  If {cmd:graph} is
specified, graphs will be produced and displayed on screen for all versions of
Stata except Stata(console).  Additionally, if graphs should be saved to disk,
the {cmd:graph_export()} option should be used.

{phang}
{opt g1on} activates the unit-specific weight graph.  By default, this option
is off because it can take considerable time to generate when many control
units are present.

{phang}
{cmd:g1_opt(}{it:{help twoway_options:graph_options}}{cmd:)} modifies the
appearance of the unit-specific weight graph.  The options adjust the
underlying scatterplot, so they should be consistent with two-way
scatterplots.

{phang}
{cmd:g2_opt(}{it:{help twoway_options:graph_options}}{cmd:)} modifies the
appearance of the outcome trend graphs.  The options adjust the underlying
line plot, so should be consistent with two-way line plots.

{phang}
{cmd:graph_export(}[{it:stub}]{cmd:,} {it:{help graph export:type}}{cmd:)}
specifies graphs will be saved as {cmd:weights}{it:YYYY} and
{cmd:trends}{it:YYYY} for each of the unit-specific weights and outcome
trends, respectively, where {it:YYYY} refers to each treatment adoption
period.  Two graphs will be generated for each treatment adoption period
provided that {cmd:g1on} is specified.  Otherwise, a single graph will be
generated for each adoption period.  If this option is specified, {it:type}
must be specified, which refers to a valid Stata graph
{it:{help graph export:type}} (for example, {cmd:.eps}, {cmd:.pdf}, or any
other options permitted by {cmd:graph_export()}).  Additionally, if {it:type}
is specified as {cmd:.gph}, the graph is saved on disk in Stata's {cmd:.gph}
format, which permits editing of the graph.  Optionally, {it:stub} can be
specified, which will be prepended to exported graph names.

{phang}
{cmd:msize(}{it:{help markersizestyle:markersizestyle}}{cmd:)} allows you to
modify the size of the marker for graph 1.

{phang}
{opt unstandardized} specifies controls will simply be entered in their
original units.  This option should be used with care.  If controls are
included and the {cmd:optimized} method is specified, controls will be
standardized as {it:z} scores prior to finding optimal weights.  This avoids
problems with optimization when control variables have very high dispersion.

{phang}
{opt mattitles} requests labels be added to the returned {cmd:e(omega)} weight
matrix providing names (in {it:string}) for the unit variables that generate
the synthetic control group in each case.  By default, the returned weight
matrix ({cmd:e(omega)}) will store these weights with a final column providing
the numerical ID of units, where this numerical ID is either taken from the
unit variable (if this variable is a numerical format) or arranged in
alphabetical order based on the unit variable if it is in string format.

{phang}
{opt verbose} requests additional output, such as warning messages if the
number of iterations specified in {cmd:max_iter()} is reached.

{phang}
{opt returnweights} indicates that estimated weights omega and lambda should
be returned directly in the dataset corresponding to each unit.  By default,
they will be returned as variables named {cmd:omega}{it:YYYY} and
{cmd:lambda}{it:YYYY}, where {it:YYYY} is replaced by treatment adoption
years.

{phang}
{opt generate(string)} specifies that the variables containing omega and
lambda weights returned if the {cmd:returnweights} option is specified should
be named starting with {it:string}.  If {cmd:returnweights} is specified but
{cmd:generate()} is not, variables will simply follow default naming.


{marker examples}{...}
{title:Examples}

{pstd}
Load data on quotas, women in parliament, and maternal mortality (a balanced
panel version) from {help sdid##Bhalotra23:Bhalotra et al. (2023)}

{phang2}
{bf:. {stata webuse set www.damianclarke.net/stata/}}
 
{phang2}
{bf:. {stata webuse quota_example}}

{pstd}
Run SDID estimator without covariates and bootstrap standard error

{phang2}
{bf:. {stata sdid womparl country year quota, vce(bootstrap) seed(1213)}}
 
{pstd}
Run SDID estimator using covariates in the projected way

{phang2}
{bf:. {stata drop if lngdp == .}}

{phang2}
{bf:. {stata sdid womparl country year quota, vce(bootstrap) seed(1213) covariates(lngdp, projected)}}

{pstd}
Example with one time adoption and some graphics options;  load data from
{help sdid##Abadie10:Abadie, Diamond, and Hainmueller (2010)}

{phang2}
{bf:. {stata webuse prop99_example, clear}}

{phang2}
{bf:. {stata sdid packspercapita state year treated, vce(placebo) seed(1213) graph g1_opt(xtitle("")) g2_opt(ylabel(0(50)150))}}


{title:Stored results}

{pstd}
{cmd:sdid} stores the following in {cmd:e()}:

{synoptset 20 tabbed}{...}
{p2col 5 20 24 2: Scalars}{p_end}
{synopt:{cmd:e(ATT)}}ATT{p_end}
{synopt:{cmd:e(ATT_l)}}left-hand point of confidence interval on ATT (based on
{cmd:level()}){p_end}
{synopt:{cmd:e(ATT_r)}}right-hand point of confidence interval on ATT (based
on {cmd:level()}){p_end}
{synopt:{cmd:e(se)}}standard error for the ATT{p_end}
{synopt:{cmd:e(reps)}}number of bootstrap or placebo replications{p_end}
{synopt:{cmd:e(N_clust)}}number of units (groups) observed in the original panel used for {cmd:sdid}{p_end}

{synoptset 20 tabbed}{...}
{p2col 5 20 24 2: Macros}{p_end}
{synopt:{cmd:e(cmd)}}{cmd:sdid}{p_end}
{synopt:{cmd:e(cmdline)}}command as typed{p_end}
{synopt:{cmd:e(depvar)}}name of dependent variable{p_end}
{synopt:{cmd:e(vce)}}{it:vcetype} specified in {cmd:vce()}
({cmd:placebo}, {cmd:bootstrap}, {cmd:jackknife}, or {cmd:noinference}){p_end}
{synopt:{cmd:e(clustvar)}}provides the name of the unit (group) variable{p_end}

{synoptset 20 tabbed}{...}
{p2col 5 20 24 2: Matrices}{p_end}
{synopt:{cmd:e(tau)}}tau estimator for each adoption time period along with its standard error{p_end}
{synopt:{cmd:e(lambda)}}lambda weights (time-specific weights){p_end}
{synopt:{cmd:e(omega)}}omega weights (unit-specific weights){p_end}
{synopt:{cmd:e(adoption)}}vector containing the list of all treatment adoption times{p_end}
{synopt:{cmd:e(beta)}}vector corresponding to coefficients estimated on
covariates included as control (returned only if the {cmd:covariates()} option is used){p_end}
{synopt:{cmd:e(series)}}control and treatment series containing time-series trends of outcome means over time{p_end}
{synopt:{cmd:e(difference)}}difference between treatment and control series over time{p_end}
{synopt:{cmd:e(b)}}coefficient estimate returned for ATT{p_end}
{synopt:{cmd:e(V)}}variance estimate returned for ATT{p_end}

{pstd}
The matrices {cmd:e(b)} and {cmd:e(V)} are included to facilitate the
exportation of results from {cmd:sdid} with commands such as {cmd:estout}
({help sdid##Jann04:Jann 2004}).


{marker references}{...}
{title:References}

{marker Abadie10}{...}
{phang}
Abadie, A., A. Diamond, and J. Hainmueller. 2010. Synthetic control methods
for comparative case studies: Estimating the effect of California's
tobacco control program.
{it:Journal of the American Statistical Association} 105: 493-505. 
{browse "https://doi.org/10.1198/jasa.2009.ap08746"}.

{marker Arkhangelsky21}{...}
{phang}
Arkhangelsky, D., S. Athey, D. A. Hirshberg, G. W. Imbens, and S. Wager.
2021. Synthetic difference-in-differences. {it:American Economic Review} 111:
4088-4118. {browse "https://doi.org/10.1257/aer.20190159"}.

{marker Bhalotra23}{...}
{phang}
Bhalotra, S., D. Clarke, J. F. Gomes, and A. Venkataramani. 2023. Maternal
mortality and women's political power. 
{it:Journal of the European Economic Association} 21:
2172-2208. {browse "https://doi.org/10.1093/jeea/jvad012"}.

{marker Clarke23}{...}
{phang}
Clarke, D., D. Paila{c n~}ir, S. Athey, and G. Imbens. 2023. 
Synthetic difference-in-differences estimation. IZA Discussion Paper 15907,
Institute of Labor Economics (IZA).

{marker Jann04}{...}
{phang}
Jann, B. 2004. estout: Stata module to make regression tables. Statistical
Software Components S439301, Department of Economics, Boston College.
{browse "https://ideas.repec.org/c/boc/bocode/s439301.html"}.

{marker Kranz22}{...}
{phang}
Kranz, S. 2022. Synthetic difference-in-differences with time-varying
covariates. GitHub.
{browse "https://github.com/skranz/xsynthdid/blob/main/paper/synthdid_with_covariates.pdf"}.


{title:Authors}

{pstd}
Damian Clarke{break}
Department of Economics{break}
University of Chile{break}
Santiago, Chile{break}
{browse "mailto:dclarke@fen.uchile.cl":dclarke@fen.uchile.cl}{break}
Website {browse "http://www.damianclarke.net/"}

{pstd}
Daniel Paila{c n~}ir{break}
Department of Economics, University of Chile{break}
Ministry of Economics, Development and Tourism{break}
Santiago, Chile{break}
{browse "mailto:dpailanir@fen.uchile.cl":dpailanir@fen.uchile.cl}{break}
{browse "https://daniel-pailanir.github.io/"}


{title:Website}

{pstd}
{cmd:sdid} is maintained at {browse "https://github.com/Daniel-Pailanir/sdid"}.


{marker see}{...}
{title:Also see}

{p 4 14 2}
Article:  {it:Stata Journal}, volume 24, number 4: {browse "https://doi.org/10.1177/1536867X241297914":st0757}{p_end}
