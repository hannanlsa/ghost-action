#!/usr/bin/env python3
"""GhostAction Windows Build Script
生成 EXE (PyInstaller) + MSI (WiX Toolset)
支持 Windows 10/11, 32/64位
"""
import PyInstaller.__main__
import os
import sys
import subprocess
import platform

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")

ARCH = "x64" if sys.maxsize > 2**32 else "x86"
VERSION = "1.7.2"


def build_exe():
    print(f"=== Building GhostAction v{VERSION} EXE ({ARCH}) ===")
    args = [
        os.path.join(ROOT, "main.py"),
        "--name=GhostAction",
        "--windowed",
        "--onefile",
        "--noconfirm",
        f"--add-data={SRC}{os.pathsep}src",
        "--hidden-import=PIL._tkinter_finder",
        "--hidden-import=pytesseract",
        "--hidden-import=cv2",
        "--hidden-import=mss",
        "--hidden-import=marketplace",
        "--hidden-import=data_source",
        "--hidden-import=ai_recognizer",
        "--hidden-import=accessibility",
        "--hidden-import=script_manager",
        "--hidden-import=win_recorder",
        "--hidden-import=win_player",
        "--hidden-import=requests",
        "--hidden-import=openpyxl",
        "--hidden-import=pyperclip",
        f"--distpath={DIST}",
        f"--workpath={BUILD}",
        f"--specpath={ROOT}",
    ]
    icon_path = os.path.join(ROOT, "scripts", "icon.ico")
    if os.path.exists(icon_path):
        args.append(f"--icon={icon_path}")
    PyInstaller.__main__.run(args)
    exe_path = os.path.join(DIST, "GhostAction.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"✅ EXE built: {exe_path} ({size_mb:.1f} MB)")
        return exe_path
    else:
        print("❌ EXE build failed")
        return None


def build_msi(exe_path):
    print(f"=== Building GhostAction v{VERSION} MSI ({ARCH}) ===")
    wix_path = _find_wix()
    if not wix_path:
        print("⚠️ WiX Toolset not found, skipping MSI build")
        print("   Install from: https://wixtoolset.org/releases/")
        return None

    wxs_path = os.path.join(ROOT, "scripts", "GhostAction.wxs")
    wixobj_path = os.path.join(BUILD, "GhostAction.wixobj")
    msi_name = f"GhostAction-v{VERSION}-Windows-{ARCH}.msi"
    msi_path = os.path.join(DIST, msi_name)

    _generate_wxs(wxs_path, exe_path, ARCH)

    candle = os.path.join(wix_path, "candle.exe")
    light = os.path.join(wix_path, "light.exe")

    subprocess.run([candle, wxs_path, "-o", wixobj_path, f"-dVersion={VERSION}", f"-dArch={ARCH}"], check=True)
    subprocess.run([light, wixobj_path, "-o", msi_path, "-ext", "WixUIExtension"], check=True)

    if os.path.exists(msi_path):
        size_mb = os.path.getsize(msi_path) / (1024 * 1024)
        print(f"✅ MSI built: {msi_path} ({size_mb:.1f} MB)")
        return msi_path
    else:
        print("❌ MSI build failed")
        return None


def _find_wix():
    for path in [
        r"C:\Program Files (x86)\WiX Toolset v3.11\bin",
        r"C:\Program Files\WiX Toolset v3.11\bin",
        r"C:\Program Files (x86)\WiX Toolset v4\bin",
        r"C:\Program Files\WiX Toolset v4\bin",
    ]:
        if os.path.exists(os.path.join(path, "candle.exe")):
            return path
    return None


def _generate_wxs(wxs_path, exe_path, arch):
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*" Name="GhostAction" Language="1033" Version="{VERSION}" Manufacturer="GhostAction" UpgradeCode="B5D3E2A1-4F6C-4D8E-9A0B-1C2D3E4F5A6B">
    <Package InstallerVersion="200" Compressed="yes" InstallScope="perMachine" Platform="{arch}" />
    <MajorUpgrade DowngradeErrorMessage="A newer version of GhostAction is already installed." />
    <MediaTemplate EmbedCab="yes" />
    <UIRef Id="WixUI_InstallDir" />
    <Property Id="WIXUI_INSTALLDIR" Value="INSTALLFOLDER" />
    <Feature Id="ProductFeature" Title="GhostAction" Level="1">
      <ComponentGroupRef Id="ProductComponents" />
    </Feature>
  </Product>
  <Fragment>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFilesFolder">
        <Directory Id="INSTALLFOLDER" Name="GhostAction" />
      </Directory>
      <Directory Id="DesktopFolder" />
      <Directory Id="ProgramMenuFolder" />
    </Directory>
  </Fragment>
  <Fragment>
    <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
      <Component Id="GhostAction.exe" Guid="*">
        <File Id="GhostAction.exe" Source="{exe_path}" KeyPath="yes" />
        <Shortcut Id="DesktopShortcut" Directory="DesktopFolder" Name="GhostAction" Target="[INSTALLFOLDER]GhostAction.exe" WorkingDirectory="INSTALLFOLDER" />
        <Shortcut Id="StartMenuShortcut" Directory="ProgramMenuFolder" Name="GhostAction" Target="[INSTALLFOLDER]GhostAction.exe" WorkingDirectory="INSTALLFOLDER" />
      </Component>
    </ComponentGroup>
  </Fragment>
</Wix>"""
    os.makedirs(os.path.dirname(wxs_path), exist_ok=True)
    with open(wxs_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    exe_path = build_exe()
    if exe_path:
        new_name = f"GhostAction-v{VERSION}-Windows-{ARCH}.exe"
        new_path = os.path.join(DIST, new_name)
        if os.path.exists(new_path):
            os.remove(new_path)
        os.rename(exe_path, new_path)
        print(f"✅ Renamed to: {new_path}")
        build_msi(new_path)