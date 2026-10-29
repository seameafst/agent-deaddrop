' Run a PowerShell script with a fully hidden window (for scheduled tasks).
' Usage: wscript.exe run_hidden.vbs "<absolute path to .ps1>"
Option Explicit
Dim shell, scriptPath, cmd
Set shell = CreateObject("WScript.Shell")
If WScript.Arguments.Count < 1 Then
    WScript.Quit 2
End If
scriptPath = WScript.Arguments(0)
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptPath & """"
' 0 = hidden window, False = do not wait
shell.Run cmd, 0, False
