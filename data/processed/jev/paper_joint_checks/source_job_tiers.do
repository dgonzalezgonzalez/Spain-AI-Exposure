* Joint discrete DiD: tiers 1 and 2 versus the omitted tier 3.
* Reuse the paper's periods, outcome transformations, FE estimator and clustering.
capture program drop run_job_tier_phase
program define run_job_tier_phase
    syntax, SPEC(string) OUTCOME(name) ABSORB(string) TIERVAR(name) [SAMPLEVAR(name)]
    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', `tiervar', cno4_id)
        assert inlist(`tiervar', 1, 2, 3)
        foreach tier in 1 2 {
            gen double tier`tier'_adjustment = (`tiervar' == `tier') * inrange(event_time, 0, 24)
            gen double tier`tier'_later = (`tiervar' == `tier') * inrange(event_time, 25, 40)
        }
        reghdfe `outcome' tier1_adjustment tier1_later tier2_adjustment tier2_later, ///
            absorb(`absorb') vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)
        test (tier1_adjustment = tier1_later) (tier2_adjustment = tier2_later)
        local equality_p = r(p)
        tempfile results
        postfile P str48 specification str32 outcome byte tier str16 phase ///
            double estimate se ci_low ci_high equality_p long observations clusters ///
            using `results', replace
        foreach tier in 1 2 {
            foreach phase in adjustment later {
                lincom tier`tier'_`phase'
                post P ("`spec'") ("`outcome'") (`tier') ("`phase'") ///
                    (r(estimate)) (r(se)) (r(lb)) (r(ub)) (`equality_p') ///
                    (`observations') (`clusters')
            }
        }
        postclose P
        use `results', clear
        export delimited using "$TAB/twfe_tier_phase_`spec'_`outcome'.csv", replace
    restore
end

capture program drop run_job_tier_event
program define run_job_tier_event
    syntax, SPEC(string) OUTCOME(name) ABSORB(string) TIERVAR(name) [SAMPLEVAR(name)]
    preserve
        keep if inrange(event_time, $ES_MIN, $ES_MAX)
        if "`samplevar'" != "" keep if `samplevar' == 1
        keep if !missing(`outcome', `tiervar', cno4_id)
        assert inlist(`tiervar', 1, 2, 3)
        quietly levelsof event_time, local(observed_events)
        local all
        local pre
        foreach tier in 1 2 {
            foreach k of local observed_events {
                if `k' != -1 {
                    if `k' < 0 local suffix "m`=abs(`k')'"
                    else local suffix "p`k'"
                    gen double tier`tier'_`suffix' = (`tiervar' == `tier') * (event_time == `k')
                    local all `all' tier`tier'_`suffix'
                    if inrange(`k', $ES_MIN, -2) local pre `pre' tier`tier'_`suffix'
                }
            }
        }
        * Both sets of event indicators enter this single regression.
        reghdfe `outcome' `all', absorb(`absorb') vce(cluster cno4_id)
        local observations = e(N)
        local clusters = e(N_clust)
        test `pre'
        local pretrend_p = r(p)
        tempfile pretrend events
        postfile P str48 specification str32 outcome double p_value ///
            long observations clusters using `pretrend', replace
        post P ("`spec'") ("`outcome'") (`pretrend_p') (`observations') (`clusters')
        postclose P
        postfile E str48 specification str32 outcome byte tier int event_time ///
            double estimate se ci_low ci_high long observations clusters using `events', replace
        foreach tier in 1 2 {
            forvalues k = $ES_MIN/$ES_MAX {
                local present : list posof "`k'" in observed_events
                if `present' == 0 {
                    post E ("`spec'") ("`outcome'") (`tier') (`k') ///
                        (.) (.) (.) (.) (`observations') (`clusters')
                }
                else if `k' == -1 {
                    post E ("`spec'") ("`outcome'") (`tier') (`k') ///
                        (0) (0) (0) (0) (`observations') (`clusters')
                }
                else {
                    if `k' < 0 local suffix "m`=abs(`k')'"
                    else local suffix "p`k'"
                    local beta = _b[tier`tier'_`suffix']
                    local standard_error = _se[tier`tier'_`suffix']
                    post E ("`spec'") ("`outcome'") (`tier') (`k') ///
                        (`beta') (`standard_error') ///
                        (`beta' - 1.96*`standard_error') (`beta' + 1.96*`standard_error') ///
                        (`observations') (`clusters')
                }
            }
        }
        postclose E
        use `pretrend', clear
        export delimited using "$TAB/twfe_tier_pretrend_`spec'_`outcome'.csv", replace
        use `events', clear
        sort tier event_time
        export delimited using "$TAB/twfe_tier_event_`spec'_`outcome'.csv", replace
    restore
end

capture program drop produce_job_tier_outputs
program define produce_job_tier_outputs
    syntax, MODEL(string)
    load_v1_panel using "$IN/est_total_cno4_`model'.csv"
    foreach outcome in ln_parados ln_contratos {
        run_job_tier_phase, spec("`model'_tiers_benchmark") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id ym_id")
        run_job_tier_phase, spec("`model'_tiers_cno1_month") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id cno1_ym")
        run_job_tier_phase, spec("`model'_tiers_cno1_month_no2021") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id cno1_ym") samplevar(sample_no2021)
        run_job_tier_event, spec("`model'_tiers_benchmark") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id ym_id")
        run_job_tier_event, spec("`model'_tiers_cno1_month") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id cno1_ym")
        run_job_tier_event, spec("`model'_tiers_cno1_month_no2021") outcome(`outcome') ///
            tiervar(`model'_tier) absorb("cno4_id cno1_ym") samplevar(sample_no2021)
    }
end
