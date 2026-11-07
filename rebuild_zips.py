from pathlib import Path
import zipfile, shutil
root=Path('.').resolve()
# source
sp=root/'FireflyDL-v1.0.0-source.zip'
if sp.exists(): sp.unlink()
excluded={'.git','.idea','.venv','venv','dist','build','__pycache__','release_tmp'}
count=0
with zipfile.ZipFile(sp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(root)
        if any(part in excluded for part in rel.parts): continue
        if p.suffix.lower() in {'.pyc','.pyo','.zip'}: continue
        z.write(p,(Path('FireflyDL')/rel).as_posix()); count+=1
print('source',count,round(sp.stat().st_size/1024/1024,2),'MB')
# release
stage=root/'release_tmp'
if stage.exists(): shutil.rmtree(stage)
stage.mkdir()
shutil.copytree(root/'dist'/'FireflyDL',stage/'FireflyDL')
shutil.copytree(root/'dist'/'FireflyDL-CLI',stage/'FireflyDL-CLI')
shutil.copytree(root/'docs',stage/'docs')
shutil.copy2(root/'README.md',stage/'README.md')
(stage/'启动 GUI.bat').write_bytes('@echo off\r\ncd /d "%~dp0"\r\nstart "" "FireflyDL\\FireflyDL.exe"\r\n'.encode())
(stage/'启动 CLI.bat').write_bytes('@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\n"FireflyDL-CLI\\FireflyDL-CLI.exe" %*\r\necho.\r\npause\r\n'.encode())
rp=root/'FireflyDL-v1.0.0-win64.zip'
if rp.exists(): rp.unlink()
count=0
with zipfile.ZipFile(rp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(stage.rglob('*')):
        if p.is_file(): z.write(p,p.relative_to(stage).as_posix()); count+=1
print('release',count,round(rp.stat().st_size/1024/1024,1),'MB')
shutil.rmtree(stage)
