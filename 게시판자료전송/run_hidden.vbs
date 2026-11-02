' board_material_send - hidden launcher for the scheduler (node watch.js).
'
' Why not point the task at node.exe directly: an Interactive task pops a
' console window every 10 minutes, and this PC has HKCU\Console\QuickEdit=1 -
' one click on that window blocks stdout and the run hangs (wm_fc 2026-09-03,
' counsel_report 2026-07-15).  Window hidden + stdout redirected = no console
' buffer to block on.  Real logging is watch.js -> watch.log; the .out file is
' only the last run's raw console, overwritten each time.
'
' !! PURE ASCII, save WITHOUT BOM (WScript 800A0408).
' Arg 1 = script to run (default watch.js).  report.js uses the same launcher.
Option Explicit
Dim fso, shell, q, dir, node, cmd, script, outfile

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

script = "watch.js"
If WScript.Arguments.Count > 0 Then script = WScript.Arguments(0)
outfile = fso.GetBaseName(script) & ".console.out"

dir = fso.GetParentFolderName(WScript.ScriptFullName)

' Holiday gate (2026-10-05): the trigger is Mon-Fri, public holidays are skipped here.
' List = wm_kiz_fc\config\public_holidays_kr.json (shared). Missing file = run anyway.
If IsHoliday() Then WScript.Quit 0

node = shell.ExpandEnvironmentStrings("%ProgramFiles%") & "\nodejs\node.exe"
If Not fso.FileExists(node) Then node = "node.exe"

q = Chr(34)
cmd = "cmd /c " & q & q & node & q & " " & q & fso.BuildPath(dir, script) & q & _
      " > " & q & fso.BuildPath(dir, outfile) & q & " 2>&1" & q

shell.CurrentDirectory = dir
WScript.Quit shell.Run(cmd, 0, True)   ' 0 = hidden / True = wait so the task gets the exit code

Function IsHoliday()
  Dim p, st, d
  IsHoliday = False
  p = fso.BuildPath(dir, "..\..\wm_kiz_fc\config\public_holidays_kr.json")
  If Not fso.FileExists(p) Then Exit Function
  Set st = CreateObject("ADODB.Stream")
  st.Charset = "utf-8": st.Open: st.LoadFromFile p
  d = Year(Date) & "-" & Right("0" & Month(Date), 2) & "-" & Right("0" & Day(Date), 2)
  IsHoliday = InStr(st.ReadText, Chr(34) & d & Chr(34)) > 0
  st.Close
End Function
