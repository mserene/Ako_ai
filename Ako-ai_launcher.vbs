Option Explicit

Dim shell, fso, appDir, bootstrap, appExe, rc, logPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
If Right(appDir, 1) <> "\" Then appDir = appDir & "\"

bootstrap = appDir & "bootstrap_runtime.bat"
appExe = appDir & "Ako-ai.exe"
logPath = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Ako-ai\runtime\bootstrap_runtime.log"

If fso.FileExists(bootstrap) Then
    rc = shell.Run("""" & bootstrap & """ --no-pause", 0, True)
    If rc <> 0 Then
        MsgBox "Ako 실행 준비 중 오류가 발생했습니다." & vbCrLf & _
               "로그 파일을 확인해 주세요:" & vbCrLf & logPath, _
               vbExclamation, "Ako"
        WScript.Quit rc
    End If
Else
    MsgBox "bootstrap_runtime.bat를 찾을 수 없습니다." & vbCrLf & bootstrap, _
           vbCritical, "Ako"
    WScript.Quit 1
End If

If fso.FileExists(appExe) Then
    shell.Run """" & appExe & """", 0, False
Else
    MsgBox "Ako-ai.exe를 찾을 수 없습니다." & vbCrLf & appExe, _
           vbCritical, "Ako"
    WScript.Quit 1
End If
