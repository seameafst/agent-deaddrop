' Launch the watchdog loop with no visible window.
' Used by the Startup-folder shortcut; no Task Scheduler involved.
Option Explicit
Dim shell, fso, scriptDir, ps1, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = scriptDir & "\watchdog_loop.ps1"
If Not fso.FileExists(ps1) Then
    WScript.Quit 3
End If
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
' 0 = hidden window, False = do not wait
shell.Run cmd, 0, False
