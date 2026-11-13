# The old suites' cases (packet al6-join, R7)

The packet's R7 table, kept beside it because 225 rows do not fit a packet's ceiling. Each case of
the old tree's five suites (as they stood before 034519c removed them, `git show 034519c^:tests/<suite>`),
by its printed name, against the test that holds it now, or the reason it stays cut. Counts:
`test-arg-handling.sh` 58, `test-run-path.sh` 26, `test-flag-pinning.sh` 14, `test-fanout.py` 46,
`test-apirun.py` 81. A looped case is one row per pass.

T1 is `tests/test_al1_run.py`, T3 `tests/test_al3_fanout.py`, J `tests/test_al6_join.py`. The cuts:
- **cut, pass-through**: the wrapper's pass-through mode is gone (design/21 §3.1 item 2); no caller
  argv reaches a shard, held by T1 `ArgvTest.test_signature_has_no_pass_through`.
- **cut, open argv**: a caller flag, override or `--output-format` form has no way in; the argv is
  built whole (T1 `ArgvTest.test_signature_has_no_pass_through`, `test_flag_pins`).
- **cut, single-run verb**: the one-agent verb and its `--help` and `--prompt-file` are gone; a shard
  is a fan-out of one.
- **cut, fold**: the stream fold and `progress.json` are gone (design/21 item 5); a shard runs
  `--output-format json` and its result file is kept.
- **cut, caller env**: the lane reads no place or key from the caller's environment (seams §1 rule 4);
  the wall denies the secret roots (`wall.SECRET_ROOTS`).
- **cut, proxy pin**: the pin is gone (design/21 item 4); `api.proxy` reaches the child, T1
  `RunTest.test_lane_proxy_reaches_the_child`.
- **cut, tags**, **cut, no-log switch**, **cut, cost tool**: the tags, the switch and the cost report
  went with the old tools; a run names its fan-out and session.
- **later, al7's sweep**: no code prunes `runs/` at this row; al7-detach's sweep owns it.

The cost tool's suite, `test-costs.py`, 76 cases: cut with the cost tool (design/21 §3.1); no row.

| # | suite | old case | held by, or cut |
|---|---|---|---|
| 1 | `test-arg-handling.sh` | profile-after-arg still emits --allowedTools | cut, pass-through |
| 2 | `test-arg-handling.sh` | profile-after-arg still emits --disallowedTools | cut, pass-through |
| 3 | `test-arg-handling.sh` | profile-after-arg still emits --permission-mode | cut, pass-through |
| 4 | `test-arg-handling.sh` | profile-after-arg still emits --max-budget-usd | cut, pass-through |
| 5 | `test-arg-handling.sh` | flag-shaped prompt is absent from argv | T1 `ArgvTest.test_prompt_never_in_argv` |
| 6 | `test-arg-handling.sh` | flag-shaped prompt delivered verbatim on stdin | T1 `RunTest.test_flag_shaped_prompt_on_stdin` |
| 7 | `test-arg-handling.sh` | flag-shaped prompt runs (it is data, not a flag) | T1 `RunTest.test_flag_shaped_prompt_on_stdin` |
| 8 | `test-arg-handling.sh` | refuses --dangerously-skip-permissions | cut, open argv |
| 9 | `test-arg-handling.sh` | refuses --allow-dangerously-skip-permissions | cut, open argv |
| 10 | `test-arg-handling.sh` | refuses --tools | cut, open argv |
| 11 | `test-arg-handling.sh` | refuses --settings | cut, open argv |
| 12 | `test-arg-handling.sh` | refuses --agents | cut, open argv |
| 13 | `test-arg-handling.sh` | refuses --agent | cut, open argv |
| 14 | `test-arg-handling.sh` | refuses --mcp-config | cut, open argv |
| 15 | `test-arg-handling.sh` | refuses --permission-mode | cut, open argv |
| 16 | `test-arg-handling.sh` | refuses --allowedTools | cut, open argv |
| 17 | `test-arg-handling.sh` | refuses --disallowedTools | cut, open argv |
| 18 | `test-arg-handling.sh` | refuses --setting-sources | cut, open argv |
| 19 | `test-arg-handling.sh` | refuses --debug-file (unlisted) | cut, open argv |
| 20 | `test-arg-handling.sh` | profile ceiling present on a normal run | T1 `ArgvTest.test_ceiling_present` |
| 21 | `test-arg-handling.sh` | refuses a leading-dash flag value | T1 `ArgvTest.test_value_rules` |
| 22 | `test-arg-handling.sh` | refuses a non-numeric --max-budget-usd | T1 `ArgvTest.test_value_rules` |
| 23 | `test-arg-handling.sh` | bare --model override replaces the profile's copy | cut, open argv |
| 24 | `test-arg-handling.sh` | joined --max-budget-usd=0.5 replaces the profile's copy | cut, open argv |
| 25 | `test-arg-handling.sh` | --model override drops the profile's --effort | cut, open argv |
| 26 | `test-arg-handling.sh` | --prompt-file delivers a regular file's contents on stdin | cut, single-run verb |
| 27 | `test-arg-handling.sh` | --prompt-file <directory> is refused, not run with an empty prompt | cut, single-run verb |
| 28 | `test-arg-handling.sh` | prompt text is not an argv token | T1 `ArgvTest.test_prompt_never_in_argv` |
| 29 | `test-arg-handling.sh` | prompt text delivered on stdin | T1 `RunTest.test_flag_shaped_prompt_on_stdin` |
| 30 | `test-arg-handling.sh` | review emits --tools "Read Grep Glob" | T1 `ArgvTest.test_each_type_emits_tools_read_grep_glob` |
| 31 | `test-arg-handling.sh` | explore emits --tools "Read Grep Glob" | T1 `ArgvTest.test_each_type_emits_tools_read_grep_glob` |
| 32 | `test-arg-handling.sh` | analyze emits --tools "Read Grep Glob" | T1 `ArgvTest.test_each_type_emits_tools_read_grep_glob` |
| 33 | `test-arg-handling.sh` | caller --tools is refused (cannot widen the toolset) | cut, open argv |
| 34 | `test-arg-handling.sh` | review emits --tools | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 35 | `test-arg-handling.sh` | review emits --allowedTools | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 36 | `test-arg-handling.sh` | review emits --disallowedTools | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 37 | `test-arg-handling.sh` | review emits --permission-mode | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 38 | `test-arg-handling.sh` | review emits --max-budget-usd | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 39 | `test-arg-handling.sh` | review emits --output-format | T1 `ArgvTest.test_review_emits_the_six_invariant_flags` |
| 40 | `test-arg-handling.sh` | explore profile emits its defaults | T1 `ArgvTest.test_explore_profile_emits_its_defaults` |
| 41 | `test-arg-handling.sh` | refuses --no-stdin after claude args in pass-through | cut, pass-through |
| 42 | `test-arg-handling.sh` | redundant --output-format json is tolerated | cut, open argv |
| 43 | `test-arg-handling.sh` | redundant --output-format=json is tolerated | cut, open argv |
| 44 | `test-arg-handling.sh` | redundant --output-format json does not duplicate the flag | T1 `ArgvTest.test_output_format_json_once` |
| 45 | `test-arg-handling.sh` | child still sees --output-format json | T1 `ArgvTest.test_output_format_json_once` |
| 46 | `test-arg-handling.sh` | refuses --output-format yaml | cut, open argv |
| 47 | `test-arg-handling.sh` | refuses --output-format=text | cut, open argv |
| 48 | `test-arg-handling.sh` | refuses --output-format stream-json | cut, open argv |
| 49 | `test-arg-handling.sh` | --help prints wrapper help | cut, single-run verb |
| 50 | `test-arg-handling.sh` | -h prints wrapper help | cut, single-run verb |
| 51 | `test-arg-handling.sh` | pass-through run gets exactly one --append-system-prompt carrying SANDBOX FACTS | cut, pass-through |
| 52 | `test-arg-handling.sh` | a caller --append-system-prompt is merged, note first, still one flag | cut, pass-through |
| 53 | `test-arg-handling.sh` | the merged note lands ahead of the caller text | cut, pass-through |
| 54 | `test-arg-handling.sh` | --no-sandbox-note passes argv through untouched | cut, pass-through |
| 55 | `test-arg-handling.sh` | the no-sandbox-note variable also skips the note | cut, pass-through |
| 56 | `test-arg-handling.sh` | acceptEdits runs get the dot-directory warning | cut, pass-through |
| 57 | `test-arg-handling.sh` | runs without acceptEdits skip the acceptEdits paragraph | cut, pass-through |
| 58 | `test-arg-handling.sh` | profile role prompt states the real toolset (Read alone, Grep/Glob absent) | T1 `ArgvTest.test_role_prompt_states_the_real_toolset` |
| 59 | `test-run-path.sh` | capture path preserves child exit code through SIGPIPE | T1 `RunTest.test_exit_codes_pass_through` |
| 60 | `test-run-path.sh` | capture path preserves child exit code without a pipe | T1 `RunTest.test_exit_codes_pass_through` |
| 61 | `test-run-path.sh` | usage logger does not inherit ANTHROPIC_API_KEY | T1 `SecretsTest`; J `EndToEndTest` |
| 62 | `test-run-path.sh` | prompt '--output-format' does not flip run to the capture path | T1 `RunTest.test_flag_shaped_prompt_on_stdin` |
| 63 | `test-run-path.sh` | SOPS_AGE_KEY_FILE='keys.txt' produces a deny rule | cut, caller env |
| 64 | `test-run-path.sh` | SOPS_AGE_KEY_FILE='./secrets/keys.txt' produces a deny rule | cut, caller env |
| 65 | `test-run-path.sh` | SOPS_AGE_KEY_FILE='the home's sops age keys.txt' produces a deny rule | cut, caller env |
| 66 | `test-run-path.sh` | --pin-proxy writes the pin in the config home | cut, proxy pin |
| 67 | `test-run-path.sh` | the pin is mode 0600 | cut, proxy pin |
| 68 | `test-run-path.sh` | and git tracks no proxy-pin.conf | cut, proxy pin |
| 69 | `test-run-path.sh` | a missing pin file takes the no-pin path | cut, proxy pin |
| 70 | `test-run-path.sh` | matching proxy is silent | cut, proxy pin |
| 71 | `test-run-path.sh` | changed proxy warns | cut, proxy pin |
| 72 | `test-run-path.sh` | pinned but absent proxy warns | cut, proxy pin |
| 73 | `test-run-path.sh` | proxy with no pin warns | cut, proxy pin |
| 74 | `test-run-path.sh` | no proxy and no pin is silent | cut, proxy pin |
| 75 | `test-run-path.sh` | NODE_OPTIONS is stripped | T1 `EnvTest.test_caller_tokens_never_arrive`, `RunTest.test_child_env_is_the_allow_list` |
| 76 | `test-run-path.sh` | NODE_EXTRA_CA_CERTS is stripped | T1 `EnvTest.test_caller_tokens_never_arrive`, `RunTest.test_child_env_is_the_allow_list` |
| 77 | `test-run-path.sh` | quality verdict distinguishes thin / ok / error | T1 `ClassifyTest.test_named_states`; T3 `LedgerTest.test_one_synced_line` (the shard line's state) |
| 78 | `test-run-path.sh` | log records sizes but not the answer text | T1 `RecordTest.test_no_prompt_or_result_text_in_run_json`; J `EndToEndTest` |
| 79 | `test-run-path.sh` | --usage surfaces spend that bought nothing | cut, cost tool; a failed shard still books: T1 `RunTest.test_api_error_is_failed` |
| 80 | `test-run-path.sh` | --usage reports terminal_reason, not the misleading subtype | T1 `ClassifyTest.test_api_error_is_error` |
| 81 | `test-run-path.sh` | tags are recorded from both --tag and the tags variable | cut, tags |
| 82 | `test-run-path.sh` | rejects malformed tag 'BadKey=x' | cut, tags |
| 83 | `test-run-path.sh` | rejects malformed tag 'noequals' | cut, tags |
| 84 | `test-run-path.sh` | rejects malformed tag 'empty=' | cut, tags |
| 85 | `test-flag-pinning.sh` | --model exists and takes a value | T1 `ArgvTest.test_flag_pins` |
| 86 | `test-flag-pinning.sh` | --fallback-model exists and takes a value | T1 `ArgvTest.test_flag_pins` |
| 87 | `test-flag-pinning.sh` | --effort exists and takes a value | T1 `ArgvTest.test_flag_pins` |
| 88 | `test-flag-pinning.sh` | --max-budget-usd exists and takes a value | T1 `ArgvTest.test_flag_pins` |
| 89 | `test-flag-pinning.sh` | --add-dir exists and takes a value | T1 `ArgvTest.test_flag_pins` |
| 90 | `test-flag-pinning.sh` | -p is boolean | T1 `ArgvTest.test_flag_pins` |
| 91 | `test-flag-pinning.sh` | --print is boolean | T1 `ArgvTest.test_flag_pins` |
| 92 | `test-flag-pinning.sh` | --tools still exists | T1 `ArgvTest.test_flag_pins` |
| 93 | `test-flag-pinning.sh` | --tools still documents restricting the built-in set | T1 `ArgvTest.test_flag_pins` |
| 94 | `test-flag-pinning.sh` | --dangerously-skip-permissions still exists (wrapper correctly refuses it) | T1 `ArgvTest.test_flag_pins` |
| 95 | `test-flag-pinning.sh` | --tools still exists (wrapper correctly refuses it) | T1 `ArgvTest.test_flag_pins` |
| 96 | `test-flag-pinning.sh` | --settings still exists (wrapper correctly refuses it) | T1 `ArgvTest.test_flag_pins` |
| 97 | `test-flag-pinning.sh` | --agents still exists (wrapper correctly refuses it) | T1 `ArgvTest.test_flag_pins` |
| 98 | `test-flag-pinning.sh` | --permission-mode still exists (wrapper correctly refuses it) | T1 `ArgvTest.test_flag_pins` |
| 99 | `test-fanout.py` | substantive result -> ok | T1 `ClassifyTest.test_substantive_result_ok` |
| 100 | `test-fanout.py` | placeholder result -> degenerate | T1 `ClassifyTest.test_placeholder_result_degenerate` |
| 101 | `test-fanout.py` | API error -> error | T1 `ClassifyTest.test_api_error_is_error` |
| 102 | `test-fanout.py` | ceiling trip -> budget_exhausted | T1 `ClassifyTest.test_ceiling_trip_budget_exhausted` |
| 103 | `test-fanout.py` | non-JSON -> unparseable | T1 `ClassifyTest.test_non_json_unparseable` |
| 104 | `test-fanout.py` | missing structured_output -> degenerate | T1 `ClassifyTest.test_missing_structured_output_degenerate` |
| 105 | `test-fanout.py` | non-zero exit when any shard is unusable | T3 `RunTest.test_one_fails` |
| 106 | `test-fanout.py` | degenerate shard explains why | T1 `ClassifyTest.test_named_states` |
| 107 | `test-fanout.py` | error shard reports terminal_reason, not subtype | T1 `ClassifyTest.test_api_error_is_error` |
| 108 | `test-fanout.py` | exit 0 when every shard is usable | T3 `RunTest.test_three_shards` |
| 109 | `test-fanout.py` | findings are aggregated | T3 `RunTest.test_three_shards` |
| 110 | `test-fanout.py` | each finding is attributed to its shard | T3 `RunTest.test_three_shards` |
| 111 | `test-fanout.py` | spend never exceeds the budget | T3 `PoolTest.test_hard_aggregate_budget` |
| 112 | `test-fanout.py` | every task is accounted for | T3 `PoolTest.test_hard_aggregate_budget` |
| 113 | `test-fanout.py` | unfundable shards are reported as skipped | T3 `PoolTest.test_hard_aggregate_budget` |
| 114 | `test-fanout.py` | skipped shard explains why | T3 `PoolTest.test_hard_aggregate_budget` |
| 115 | `test-fanout.py` | shard ceiling is below its reservation | T3 `PoolTest.test_ceiling_below_grant` |
| 116 | `test-fanout.py` | hung shard -> timeout | T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 117 | `test-fanout.py` | timed-out shard books its reservation as spent | T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 118 | `test-fanout.py` | timeout explains that spend is forfeited | T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 119 | `test-fanout.py` | dry run reports the plan | T3 `PlanTest.test_shape_and_nothing_written` |
| 120 | `test-fanout.py` | dry run launches nothing | T3 `PlanTest.test_shape_and_nothing_written` |
| 121 | `test-fanout.py` | V1: clean 'no defects found' answer is accepted | T1 `ClassifyTest.test_v1_clean_answer_accepted` |
| 122 | `test-fanout.py` | V2: one terse finding does not poison a substantive shard | T1 `ClassifyTest.test_v2_one_terse_finding_does_not_poison` |
| 123 | `test-fanout.py` | genuine placeholder output is still rejected | T1 `ClassifyTest.test_genuine_placeholder_still_rejected` |
| 124 | `test-fanout.py` | garbage shard books its reservation as an estimate, not $0 | T3 `PoolTest.test_no_cost_books_grant`; T1 `RunTest.test_no_cost_books_the_grant` |
| 125 | `test-fanout.py` | aggregate flags spend as an upper bound | T3 `PoolTest.test_no_cost_books_grant`; T1 `RunTest.test_no_cost_books_the_grant` |
| 126 | `test-fanout.py` | spend stays finite and bounded despite a NaN cost | T3 `PoolTest.test_nan_cost_cannot_poison_the_pool` |
| 127 | `test-fanout.py` | a NaN shard does not starve or over-fund later shards | T3 `PoolTest.test_nan_cost_cannot_poison_the_pool` |
| 128 | `test-fanout.py` | --claude-arg with --max-budget-usd is rejected | T3 `JobTest.test_five_flags_refused` |
| 129 | `test-fanout.py` | sub-viable-ceiling reservation is skipped | T3 `PoolTest.test_floor_judged_on_ceiling_not_reservation` |
| 130 | `test-fanout.py` | 1.2x overshoot (measured rate) stays within budget | T3 `PoolTest.test_overshoot` |
| 131 | `test-fanout.py` | 1.2x overshoot still accounts for every shard | T3 `PoolTest.test_overshoot` |
| 132 | `test-fanout.py` | 2.0x overshoot (beyond margin) stays bounded | T3 `PoolTest.test_overshoot` |
| 133 | `test-fanout.py` | 2.0x overshoot still accounts for every shard | T3 `PoolTest.test_overshoot` |
| 134 | `test-fanout.py` | ceiling survives flag-shaped prompt via --tasks file | T1 `RunTest.test_flag_shaped_prompt_on_stdin`, `ArgvTest.test_ceiling_present` |
| 135 | `test-fanout.py` | ceiling survives flag-shaped prompt via positional after -- | T1 `RunTest.test_flag_shaped_prompt_on_stdin`, `ArgvTest.test_ceiling_present` |
| 136 | `test-fanout.py` | flag-shaped bare positional fails loudly rather than running | T3 `JobTest.test_five_flags_refused` (`job.flag`) |
| 137 | `test-fanout.py` | delegates were actually running before the interrupt | T3 `SignalTest` (exit 1 now; the stop books each shard `signal:<NAME>`) |
| 138 | `test-fanout.py` | no delegate survives the interrupt | T3 `SignalTest` (exit 1 now; the stop books each shard `signal:<NAME>`) |
| 139 | `test-fanout.py` | interrupted fan-out exits 130 | T3 `SignalTest` (exit 1 now; the stop books each shard `signal:<NAME>`) |
| 140 | `test-fanout.py` | interrupt reports that spend is forfeited | T3 `SignalTest` (exit 1 now; the stop books each shard `signal:<NAME>`) |
| 141 | `test-fanout.py` | every shard sees the fan-out's run id, not the caller's | T3 `RunTest.test_three_shards` |
| 142 | `test-fanout.py` | aggregate JSON is written | J `EndToEndTest` (the settle line, the ended record) |
| 143 | `test-fanout.py` | per-shard envelope kept | T1 `RecordTest.test_modes` |
| 144 | `test-fanout.py` | per-shard stderr kept | T1 `RecordTest.test_modes` |
| 145 | `test-apirun.py` | the run exits 0 | T1 `RunTest.test_ok_with_the_envelopes_cost` |
| 146 | `test-apirun.py` | stdout is the one result envelope, as --output-format json gave | T1 `RunTest.test_ok_with_the_envelopes_cost` |
| 147 | `test-apirun.py` | profile mode asks for --output-format stream-json --verbose | cut, fold |
| 148 | `test-apirun.py` | usage.jsonl gets its one row from the result event | T3 `LedgerTest.test_one_synced_line` |
| 149 | `test-apirun.py` | one run dir, named <UTC stamp>-<pid> | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (named `<fanout>-<NN>` now) |
| 150 | `test-apirun.py` | the run dir is mode 0700 | T1 `RecordTest.test_modes` |
| 151 | `test-apirun.py` | run.json carries exactly the ruled keys, plus rc and ended | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (tags cut) |
| 152 | `test-apirun.py` | id, pid, profile, tags and model | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (tags cut) |
| 153 | `test-apirun.py` | parent_session is the session id; fanout is the fan-out's run | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (tags cut) |
| 154 | `test-apirun.py` | at exit: state done, rc 0, ended | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (tags cut) |
| 155 | `test-apirun.py` | the id's stamp is UTC | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` (tags cut) |
| 156 | `test-apirun.py` | progress.json carries exactly the ruled keys | cut, fold |
| 157 | `test-apirun.py` | turns count distinct message ids (msg_1 twice is one) | cut, fold |
| 158 | `test-apirun.py` | model and the newest tool_use's name and time | cut, fold |
| 159 | `test-apirun.py` | usage is the newest message's, so status reads its context from it | cut, fold |
| 160 | `test-apirun.py` | cost_usd is predicted_cost over each message.id once | cut, fold |
| 161 | `test-apirun.py` | a repeated message.id is not counted twice | cut, fold |
| 162 | `test-apirun.py` | no prompt, thinking, text, tool input, tool result or result text in the run dir | T1 `RecordTest.test_no_prompt_or_result_text_in_run_json` |
| 163 | `test-apirun.py` | the run dir holds run.json and progress.json only | cut, fold; the result and stderr sit beside run.json now: T1 `RecordTest.test_modes` |
| 164 | `test-apirun.py` | every file in the run dir is 0600, run.json after run_end too | T1 `RecordTest.test_modes` |
| 165 | `test-apirun.py` | no trailing newline in, none out | cut, fold |
| 166 | `test-apirun.py` | mid-run: run.json reads running, with no rc or ended | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` |
| 167 | `test-apirun.py` | mid-run: run.json's pid is the live wrapper's | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` |
| 168 | `test-apirun.py` | mid-run: progress.json shows the first message and its tool while the stream pauses | cut, fold |
| 169 | `test-apirun.py` | the slow run still ends with the envelope | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` |
| 170 | `test-apirun.py` | and run.json reads done after it | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` |
| 171 | `test-apirun.py` | run.json's exit rewrite is a new file renamed into place | T1 `RecordTest.test_run_json_at_the_start_and_at_the_end` |
| 172 | `test-apirun.py` | the child's exit code passes through | T1 `RunTest.test_exit_codes_pass_through` |
| 173 | `test-apirun.py` | stdout gets nothing, as before | cut, single-run verb; the fan-out prints a shard line |
| 174 | `test-apirun.py` | no usage.jsonl row | reversed: a crashed shard books its grant, T3 `PoolTest.test_no_cost_books_grant` |
| 175 | `test-apirun.py` | run.json reads failed, rc 3 | T1 `RunTest.test_exit_codes_pass_through` |
| 176 | `test-apirun.py` | progress.json holds what the stream got to | cut, fold |
| 177 | `test-apirun.py` | rc 0 with no result event: stdout empty, run.json failed with rc 0 | T1 `ClassifyTest.test_non_json_unparseable` |
| 178 | `test-apirun.py` | a result then rc 7: the envelope prints, rc 7, run.json failed | T1 `RunTest.test_exit_codes_pass_through` |
| 179 | `test-apirun.py` | pass-through --output-format json: stdout unchanged | cut, pass-through |
| 180 | `test-apirun.py` | pass-through --output-format json: the caller's flags, no stream | cut, pass-through |
| 181 | `test-apirun.py` | pass-through --output-format json: run.json done, profile and model null | cut, pass-through |
| 182 | `test-apirun.py` | pass-through --output-format json: no progress.json | cut, pass-through |
| 183 | `test-apirun.py` | pass-through --output-format json: no prompt in run.json | cut, pass-through |
| 184 | `test-apirun.py` | pass-through text: stdout unchanged | cut, pass-through |
| 185 | `test-apirun.py` | pass-through text: the caller's flags, no stream | cut, pass-through |
| 186 | `test-apirun.py` | pass-through text: run.json done, profile and model null | cut, pass-through |
| 187 | `test-apirun.py` | pass-through text: no progress.json | cut, pass-through |
| 188 | `test-apirun.py` | pass-through text: no prompt in run.json | cut, pass-through |
| 189 | `test-apirun.py` | NO_LOG: no run dir, the old json flags, the envelope on stdout | cut, no-log switch |
| 190 | `test-apirun.py` | the pruning run exits 0 | later, al7's sweep |
| 191 | `test-apirun.py` | done and failed runs that ended over 7 days ago are removed | later, al7's sweep |
| 192 | `test-apirun.py` | a run that ended 6 days ago is kept | later, al7's sweep |
| 193 | `test-apirun.py` | a running dir whose pid is live is kept, however old | later, al7's sweep |
| 194 | `test-apirun.py` | a running dir whose pid is gone, started over 7 days ago, goes | later, al7's sweep |
| 195 | `test-apirun.py` | a running dir whose pid is gone, started 6 days ago, is kept | later, al7's sweep |
| 196 | `test-apirun.py` | a dir not named like a run id is never touched | later, al7's sweep |
| 197 | `test-apirun.py` | a kept running dir with a dead pid is left as written | later, al7's sweep |
| 198 | `test-apirun.py` | the fold exits 0 on garbage lines | cut, fold |
| 199 | `test-apirun.py` | its stdout is the result event, one line | cut, fold |
| 200 | `test-apirun.py` | the last event's progress is written | cut, fold |
| 201 | `test-apirun.py` | it writes progress.json and no temp file | cut, fold |
| 202 | `test-apirun.py` | 3000 events, no result: nothing on stdout, the last event's count written | cut, fold |
| 203 | `test-apirun.py` | result line ending \n: stdout is the line's own bytes | cut, fold |
| 204 | `test-apirun.py` | result line ending empty: stdout is the line's own bytes | cut, fold |
| 205 | `test-apirun.py` | result line ending \r\n: stdout is the line's own bytes | cut, fold |
| 206 | `test-apirun.py` | a model or tool name outside the charset is ? | cut, fold |
| 207 | `test-apirun.py` | an 81-character model is ?; an MCP tool name stays | cut, fold |
| 208 | `test-apirun.py` | 30 events over 1.5 s: at most a write a second, and the last one | cut, fold |
| 209 | `test-apirun.py` | each write is a new file renamed into place | cut, fold |
| 210 | `test-apirun.py` | profile SIGTERM: the child is gone when the wrapper exits | T3 `SignalTest.test_sigterm`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 211 | `test-apirun.py` | profile SIGTERM: the wrapper exits, stdout empty | T3 `SignalTest.test_sigterm`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 212 | `test-apirun.py` | profile SIGTERM: run.json reads failed | T3 `SignalTest.test_sigterm`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 213 | `test-apirun.py` | pass-through SIGTERM: the child is gone when the wrapper exits | cut, pass-through |
| 214 | `test-apirun.py` | pass-through SIGTERM: the wrapper exits, stdout empty | cut, pass-through |
| 215 | `test-apirun.py` | pass-through SIGTERM: run.json reads failed | cut, pass-through |
| 216 | `test-apirun.py` | pass-through SIGHUP: the child is gone when the wrapper exits | cut, pass-through |
| 217 | `test-apirun.py` | pass-through SIGHUP: the wrapper exits, stdout empty | cut, pass-through |
| 218 | `test-apirun.py` | pass-through SIGHUP: run.json reads failed | cut, pass-through |
| 219 | `test-apirun.py` | profile SIGINT: the child is gone when the wrapper exits | T3 `SignalTest.test_sigint`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 220 | `test-apirun.py` | profile SIGINT: the wrapper exits, stdout empty | T3 `SignalTest.test_sigint`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 221 | `test-apirun.py` | profile SIGINT: run.json reads failed | T3 `SignalTest.test_sigint`; T1 `RunTest.test_the_sleeper_is_timeout_and_its_group_is_gone` |
| 222 | `test-apirun.py` | no child ran on after its wrapper was signalled | T3 `SignalTest` |
| 223 | `test-apirun.py` | the wrapper says so on stderr and exits 1 | cut, fold |
| 224 | `test-apirun.py` | run.json reads failed, rc 1 | cut, fold |
| 225 | `test-apirun.py` | a caller's exported log path is left alone | cut, caller env |
