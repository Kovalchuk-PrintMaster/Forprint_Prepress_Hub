# ForPrint GDL W2.7-C3B: reviewed source candidate for limited native AI execution.
# This is NOT authorized to launch. The public entrypoint allows REVIEW ONLY.
# The private execution function is inert until a separately reviewed Blueprint
# authority/fencing adapter exists. NEVER launch/dot-source this on PREPRESS now.
param([ValidateSet('review')][string]$Mode='review')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId='gdl-w27c-native-001'
$AttemptId='a0001'
$PackageSha='d1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
$JsxSha='98780bcd7939df58f16aa0e123ced5efc4956ed43cc6438d0516b43d4d819902'
$Root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt=Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$Input=Join-Path $Attempt 'input'
$Work=Join-Path $Attempt 'work'
$Export=Join-Path $Attempt 'export'
$Archive=Join-Path $Input 'task_package.zip'
$StagingReceipt=Join-Path $Work 'staging_receipt.json'
$Claim=Join-Path $Work 'start_claim.json'
$RunningMarker=Join-Path $Work 'execution_started.json'
$JsxFile=Join-Path $Input 'main.jsx'
$NativeFile=Join-Path $Export 'native_result.ai'
$ResultFile=Join-Path $Export 'worker_result.json'
$ResultSchema='gdl_w27c3b_native_worker_result_v0_1'
$ReviewedExecutionAuthorityImplemented=$false
function Fail([string]$Code) { throw ('W27C3B_BLOCKED:'+$Code) }
function Sha([byte[]]$Bytes) {
    $h=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($h.ComputeHash($Bytes)).Replace('-','').ToLowerInvariant() }
    finally { $h.Dispose() }
}
function Regular([string]$Path) {
    $i=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if($i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail 'UNSAFE_REGULAR_FILE' }
    return $i
}
function Directory([string]$Path) {
    $i=Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if(-not $i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail 'UNSAFE_DIRECTORY' }
}
# Same narrow DEV-only ACL baseline as W2.7-B. Production access is not approved.
$OperatorSid='S-1-5-21-3087849371-1068859030-1179031902-1001'
function VerifyDevAcl([string]$Path,[bool]$Protected) {
    $acl=Get-Acl -LiteralPath $Path -ErrorAction Stop
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if([bool]$acl.AreAccessRulesProtected -ne $Protected) { Fail 'ACL_INHERITANCE_INVALID' }
    if($owner -notin @('S-1-5-32-544',$OperatorSid)) { Fail 'ACL_OWNER_INVALID' }
    if($Path -in @('D:\ForPrint_Automation',$Root,(Join-Path $Root 'jobs')) -and
       $owner -ne 'S-1-5-32-544') { Fail 'WORKSPACE_OWNER_INVALID' }
    $aces=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($aces.Count -ne 3) { Fail 'ACL_COUNT_INVALID' }
    $who=@('S-1-5-18','S-1-5-32-544',$OperatorSid)
    $seen=@{}
    $flags=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $full=[int][Security.AccessControl.FileSystemRights]::FullControl
    foreach($ace in $aces) {
        $sid=$ace.IdentityReference.Value
        $rights=[int]$ace.FileSystemRights
        if($who -notcontains $sid -or $seen.ContainsKey($sid)) { Fail 'ACL_PRINCIPAL_INVALID' }
        $seen[$sid]=$true
        if($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
           $ace.InheritanceFlags -ne $flags -or
           $ace.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
           [bool]$ace.IsInherited -eq $Protected -or
           ($rights -band $full) -ne $full -or
           ($rights -band (-bnot $full)) -ne 0) { Fail 'ACL_RIGHTS_INVALID' }
    }
    foreach($sid in $who) { if(-not $seen.ContainsKey($sid)) { Fail 'ACL_PRINCIPAL_MISSING' } }
}
function WriteOnce([string]$Path,[byte[]]$Bytes) {
    $stream=[IO.File]::Open($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true) }
    finally { $stream.Dispose() }
}
function Utf8([object]$Doc) {
    return [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $Doc -Compress -Depth 7))
}
function SourceBindings {
    # No unpack until exact ZIP/staging proof. No customer paths or SMB.
    foreach($p in @('D:\ForPrint_Automation',$Root,(Join-Path $Root 'jobs'),
            (Join-Path (Join-Path $Root 'jobs') $TaskId),$Attempt,$Input,$Work,$Export)) {
        Directory $p
        VerifyDevAcl $p ($p -eq 'D:\ForPrint_Automation')
    }
    $p=Regular $Archive
    if($p.Length -ne 5120 -or
       (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $PackageSha) {
        Fail 'ARCHIVE_BINDING_INVALID'
    }
    $r=Regular $StagingReceipt
    if($r.Length -lt 100 -or $r.Length -gt 8192) { Fail 'RECEIPT_SIZE_INVALID' }
    $receipt=Get-Content -LiteralPath $StagingReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
    if($receipt.schema_version -ne 'gdl_w27b_windows_stage_receipt_v0_1' -or
       $receipt.state -ne 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED' -or
       $receipt.task_id -cne $TaskId -or $receipt.attempt_id -cne $AttemptId -or
       $receipt.archive_sha256 -cne $PackageSha -or [long]$receipt.archive_bytes -ne 5120 -or
       $receipt.worker_launch_authorized -ne $false -or $receipt.production_ready -ne $false) {
        Fail 'STAGING_RECEIPT_INVALID'
    }
    foreach($p in @($RunningMarker,$JsxFile,$NativeFile,$ResultFile)) {
        if(Test-Path -LiteralPath $p) { Fail 'EXISTING_ATTEMPT_EVIDENCE_NO_RERUN' }
    }
    Add-Type -AssemblyName System.IO.Compression
    $fs=[IO.File]::Open($Archive,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        $zip=[IO.Compression.ZipArchive]::new($fs,[IO.Compression.ZipArchiveMode]::Read,$false)
        try {
            if($zip.Entries.Count -ne 2) { Fail 'PACKAGE_MEMBERS_INVALID' }
            $entry=$zip.GetEntry('input/main.jsx')
            $manifestEntry=$zip.GetEntry('task_manifest.json')
            if($null -eq $entry -or $null -eq $manifestEntry -or
               $entry.Length -ne 3791 -or $manifestEntry.Length -gt 32768) { Fail 'PACKAGE_ENTRY_INVALID' }
            $stm=$entry.Open()
            try {
                $mem=[IO.MemoryStream]::new()
                try { $stm.CopyTo($mem);$payload=$mem.ToArray() }
                finally { $mem.Dispose() }
            } finally { $stm.Dispose() }
            if($payload.Length -ne 3791 -or (Sha $payload) -cne $JsxSha) { Fail 'JSX_DIGEST_INVALID' }
            $reader=[IO.StreamReader]::new($manifestEntry.Open(),[Text.Encoding]::UTF8)
            try { $m=$reader.ReadToEnd() | ConvertFrom-Json }
            finally { $reader.Dispose() }
            if($m.schema_version -ne 'gdl_illustrator_task_package_v0_1' -or
               $m.task_id -cne $TaskId -or $m.attempt_id -cne $AttemptId -or
               $m.data_class -ne 'SYNTHETIC_ONLY' -or $m.adapter_id -ne 'illustrator' -or
               $m.script_path -cne 'input/main.jsx' -or
               $m.authority.worker_launch -ne $false -or
               $m.authority.dispatch_authorized -ne $false -or
               $m.inputs.Count -ne 1 -or $m.inputs[0].sha256 -cne $JsxSha -or
               $m.expected_outputs.Count -ne 2 -or
               @($m.expected_outputs | Where-Object {$_.path -eq 'export/native_result.ai'}).Count -ne 1 -or
               @($m.expected_outputs | Where-Object {$_.path -eq 'export/worker_result.json'}).Count -ne 1) {
                Fail 'MANIFEST_INVALID'
            }
            return $payload
        } finally { $zip.Dispose() }
    } finally { $fs.Dispose() }
}
function ProveLimitedInteractive([int]$ExpectedSessionId) {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $identity.Name -ine 'PREPRESS\Work') { Fail 'ACCOUNT_INVALID' }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ForPrintW27C3BToken {
  [DllImport("advapi32.dll",SetLastError=true)]
  public static extern bool GetTokenInformation(IntPtr handle,int cls,out int value,int length,out int returned);
}
'@
    $token=$identity.Token
    $x=0;$returned=0
    if(-not [ForPrintW27C3BToken]::GetTokenInformation($token,20,[ref]$x,4,[ref]$returned)) { Fail 'TOKEN_ELEVATED_QUERY' }
    if([int]$x -ne 0) { Fail 'ELEVATED_TOKEN' }
    if(-not [ForPrintW27C3BToken]::GetTokenInformation($token,18,[ref]$x,4,[ref]$returned)) { Fail 'TOKEN_TYPE_QUERY' }
    if([int]$x -ne 3) { Fail 'TOKEN_NOT_LIMITED' }
    $sid=[Diagnostics.Process]::GetCurrentProcess().SessionId
    if($sid -le 0 -or $sid -ne $ExpectedSessionId -or
       -not [Environment]::UserInteractive) { Fail 'SESSION_INVALID' }
    $list=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sid })
    if($list.Count -ne 1) { Fail 'ILLUSTRATOR_PROCESS_NOT_UNIQUE' }
    return [ordered]@{ session_id=[int]$sid;preexisting_illustrator_pid=[int]$list[0].Id;token_limited_verified=$true }
}
function Invoke-NativeCandidate([int]$ExpectedSessionId,[object]$BlueprintAuthorityProof) {
    # FAIL CLOSED: no approved authorization proof parser/owner/TTL exists yet.
    # Deliberately unreachable from public -Mode review entrypoint.
    if(-not $ReviewedExecutionAuthorityImplemented) { Fail 'BLUEPRINT_EXECUTION_GATE_NOT_IMPLEMENTED' }
    if($null -eq $BlueprintAuthorityProof) { Fail 'INDEPENDENT_AUTHORITY_PROOF_ABSENT' }
    $phase='INPUT_VALIDATION';$success=$false;$nativeSha=$null;$nativeBytes=$null
    $identity=$null;$errorCode='NOT_STARTED';$comAttached=$false;$jsxExecuted=$false
    try {
        $payload=SourceBindings
        $phase='TOKEN_AND_SESSION';$identity=ProveLimitedInteractive $ExpectedSessionId
        if(-not (Test-Path -LiteralPath $Claim -PathType Leaf)) { Fail 'PRE_DISPATCH_CLAIM_ABSENT' }
        $claim=Get-Content -LiteralPath $Claim -Raw -Encoding UTF8 | ConvertFrom-Json
        if($claim.task_id -cne $TaskId -or $claim.attempt_id -cne $AttemptId -or
           $claim.package_sha256 -cne $PackageSha -or $claim.jsx_sha256 -cne $JsxSha) {
            Fail 'START_CLAIM_BINDING_INVALID'
        }
        $phase='SINGLE_USE_MARKER'
        WriteOnce $RunningMarker (Utf8 ([ordered]@{
            schema_version='gdl_w27c3b_execution_marker_v0_1';task_id=$TaskId
            attempt_id=$AttemptId;package_sha256=$PackageSha;jsx_sha256=$JsxSha
        }))
        $phase='EXTRACT_REVIEWED_JSX'
        WriteOnce $JsxFile $payload
        if((Get-FileHash -LiteralPath $JsxFile -Algorithm SHA256).Hash.ToLowerInvariant() -cne $JsxSha) {
            Fail 'EXTRACTED_SOURCE_CHANGED'
        }
        $phase='COM_ATTACH'
        $app=[Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
        if($null -eq $app) { Fail 'COM_OBJECT_ABSENT' }
        $comAttached=$true
        $phase='JSX_EXECUTION'
        $quoted=$JsxFile.Replace('\','/')
        $value=[string]$app.DoJavaScript('$.evalFile(new File(' + "'" + $quoted + "'" + '));')
        $jsxExecuted=$true
        if($value -cne 'FORPRINT_W27C_SYNTHETIC_NATIVE_REOPENED') { Fail 'JSX_PROOF_FAILED' }
        $phase='NATIVE_RESULT_VERIFY'
        $after=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $ExpectedSessionId })
        if($after.Count -ne 1 -or $after[0].Id -ne $identity.preexisting_illustrator_pid) { Fail 'ILLUSTRATOR_PID_CHANGED' }
        $file=Regular $NativeFile
        if($file.Length -lt 1000) { Fail 'NATIVE_OUTPUT_TOO_SMALL' }
        $nativeBytes=[long]$file.Length
        $nativeSha=(Get-FileHash -LiteralPath $NativeFile -Algorithm SHA256).Hash.ToLowerInvariant()
        $success=$true;$errorCode='NONE';$phase='DONE'
    } catch {
        $errorCode='FAILED_PRESERVE_EVIDENCE'
    } finally {
        $doc=[ordered]@{
            schema_version=$ResultSchema
            state= $(if($success){'NATIVE_AI_REOPENED_LOCAL'}else{'BLOCKED_NATIVE_EXECUTION_PRESERVE_EVIDENCE'})
            task_id=$TaskId;attempt_id=$AttemptId;host='PREPRESS';windows_account='PREPRESS\Work'
            package_sha256=$PackageSha;jsx_sha256=$JsxSha
            runner_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
            session_id=$(if($identity){$identity.session_id}else{$null})
            preexisting_illustrator_pid=$(if($identity){$identity.preexisting_illustrator_pid}else{$null})
            token_limited_verified=$(if($identity){$identity.token_limited_verified}else{$false})
            com_attach_performed=$comAttached;illustrator_executed=$jsxExecuted
            native_ai_saved_reopened=$success;editable_area_text=$success
            native_ai_sha256=$nativeSha;native_ai_bytes=$nativeBytes
            phase=$phase;error_code=$errorCode
            independent_acceptance=$false;execution_authority_review_pending=$true
            production_ready=$false;accepted=$false;client_files_touched=$false
            smb_mutation=$false;cleanup_executed=$false;automatic_retry=$false
        }
        # WriteOnce output; if previous result exists, preserve it and STOP.
        WriteOnce $ResultFile (Utf8 $doc)
    }
    if(-not $success) { Fail 'NATIVE_EXECUTION_BLOCKED' }
}
# PUBLIC ENTRYPOINT: never invokes private candidate and never mutates Windows.
if($Mode -ne 'review' -or $ReviewedExecutionAuthorityImplemented) {
    Fail 'PUBLIC_EXECUTION_NOT_AUTHORIZED'
}
[Console]::Out.WriteLine((ConvertTo-Json -InputObject ([ordered]@{
    schema_version='gdl_w27c3b_native_runner_source_review_v0_1'
    state='EXECUTION_ADAPTER_SOURCE_REVIEW_ONLY_AUTHORITY_PENDING'
    task_id=$TaskId;attempt_id=$AttemptId;package_sha256=$PackageSha
    jsx_sha256=$JsxSha;worker_launch_implemented=$false
    execution_authorized=$false;com_attach_performed=$false
    illustrator_executed=$false;windows_mutation=$false
    production_ready=$false;accepted=$false
}) -Compress -Depth 4))
# NO_DISPATCH, NO_AUTOMATIC_CLEANUP, NO_SMB_OR_CUSTOMER_DATA, NO_AUTOMATIC_ACCEPT.
