; NSIS custom hooks for electron-builder.
; These macros are invoked automatically by electron-builder during install/uninstall.
; They register and remove the FideonOS Device Service via a helper executable.

!macro customInstall
  ; After app files are copied, install the Windows service.
  ; We run the Electron app itself with a special --install-service flag
  ; that triggers service-installer.ts#installService().
  DetailPrint "Installing FideonOS Device Service..."
  ExecWait '"$INSTDIR\Fideon OS.exe" --install-service' $0
  DetailPrint "Service install exit code: $0"
!macroend

!macro customUninstall
  ; Before app files are removed, uninstall the Windows service.
  DetailPrint "Removing FideonOS Device Service..."
  ExecWait '"$INSTDIR\Fideon OS.exe" --uninstall-service' $0
  DetailPrint "Service uninstall exit code: $0"
!macroend
