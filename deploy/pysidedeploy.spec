[app]
title = PlainSpeak
project_dir = .
input_file = desktop_main.py
exec_directory = dist
project_file =
icon =

[python]
python_path =
packages = Nuitka==4.1.1
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]
qml_files =
excluded_qml_plugins = QtQuick,QtQuick3D,QtCharts,QtWebEngine,QtTest,QtSensors
modules = Core,Gui,Widgets
plugins = platforms,styles,imageformats,iconengines,platformthemes

[android]
wheel_pyside =
wheel_shiboken =
plugins =

[nuitka]
macos.permissions =
mode = standalone
extra_args = --noinclude-qt-translations --include-package=plainspeak --include-package-data=plainspeak --include-data-files=../plainspeak/core/syllable_data.bin=plainspeak/core/syllable_data.bin --nofollow-import-to=flask --nofollow-import-to=docx --nofollow-import-to=pypdf --nofollow-import-to=pytest --company-name=PlainSpeak --product-name=PlainSpeak
