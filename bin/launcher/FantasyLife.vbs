' Fantasy Life PC - start the launcher window without a console window.
' The desktop shortcut points here (wscript.exe); play.bat does the same job
' with a short console flash when VBScript is not available.
Option Explicit
Dim shell, fso, root, ps, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' <install>\bin\launcher\FantasyLife.vbs -> <install>
root = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
ps = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
If Not fso.FileExists(ps) Then ps = "powershell.exe"
If Not fso.FileExists(root & "\play.ps1") Then
    MsgBox "play.ps1 was not found in " & root & ".", vbExclamation, "Fantasy Life"
    WScript.Quit 1
End If
shell.CurrentDirectory = root
cmd = """" & ps & """ -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & root & "\play.ps1"" -Window -Hidden"
shell.Run cmd, 0, False
