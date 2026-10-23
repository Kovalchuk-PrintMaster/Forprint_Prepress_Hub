# ForPrint GDL W2.7-C3A: NON-EXECUTABLE DESIGN ARTIFACT; NO WORKER LAUNCH.
# This is not a COM Runner. Blueprint/operator execution authority is pending.
# Only review mode exists. No filesystem write, Task Scheduler, COM or JSX.
param([ValidateSet('review')][string]$Mode = 'review')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId = '__TASK_ID__'
$AttemptId = '__ATTEMPT_ID__'
$ArchiveSha = '__ARCHIVE_SHA__'
$JsxSha = '__JSX_SHA__'
$ResultSchema = 'gdl_w27c3_worker_result_contract_v0_1'
$ResultFile = 'export/worker_result.json'
$NativeFile = 'export/native_result.ai'
$AttemptPolicy = [ordered]@{
    new_only_claim = $true
    no_rerun_if_claim_exists = $true
    no_overwrite_result = $true
    no_automatic_cleanup = $true
    limited_token_required = $true
    existing_interactive_illustrator_required = $true
    independent_artifact_sha_required = $true
    no_customer_files = $true
}
# NEVER replace this with a launch route without an independently approved
# execution authority and a reviewed implementation of the execution adapter.
$ExecutionAuthorized = $false
$LaunchImplemented = $false
if ($Mode -ne 'review' -or $ExecutionAuthorized -or $LaunchImplemented) {
    throw 'W27C3A_AUTHORITY_OR_IMPLEMENTATION_CHANGED'
}
$Result = [ordered]@{
    schema_version = $ResultSchema
    state = 'RUNNER_SOURCE_DRAFT_AUTHORITY_PENDING'
    task_id = $TaskId
    attempt_id = $AttemptId
    package_sha256 = $ArchiveSha
    jsx_sha256 = $JsxSha
    expected_native_output = $NativeFile
    expected_machine_output = $ResultFile
    execution_authorized = $false
    runner_launch_implemented = $false
    illustrator_executed = $false
    com_attach_performed = $false
    scheduled_tasks_mutated = $false
    windows_mutation = $false
    accepted = $false
    production_ready = $false
    cleanup_executed = $false
    attempt_policy = $AttemptPolicy
}
[Console]::Out.WriteLine((ConvertTo-Json -InputObject $Result -Compress -Depth 6))
