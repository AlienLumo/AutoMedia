' Hidden launcher for BiliDeepCollect.
' Scheduled task runs:  wscript.exe //nologo collect_hidden.vbs
' Window style 0 = hidden, False = do not wait.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
d = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c """ & d & "\collect_run.cmd""", 0, False
