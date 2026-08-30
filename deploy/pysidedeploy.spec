# Frozen desktop build, via the official Qt for Python deployment path.
#
# Checked in, and deliberately free of absolute paths. `pyside6-deploy --init`
# writes a spec full of them — the interpreter it happened to run under, the
# directory it happened to be in, an icon from inside the PySide6 wheel — and a
# build that only works on the machine that generated its configuration is not a
# build anybody can reproduce.
#
# The settings that matter, in order of how badly their absence would hurt:
#
# `--include-package-data=plainspeak` is the one. PlainSpeak carries a 1.8 MB
# syllable dictionary, 222 rule YAML files and five profile YAML files, and none
# of them is a Python module. Without this the application launches, opens a
# document, loads zero rules and quietly produces different answers — which is
# exactly the defect this project has already shipped twice through
# `package-data`, both times invisible to everyone developing on it. The
# self-test exists to make it visible, and this line is what it checks.
#
# `standalone` rather than `onefile`, because a one-file build unpacks itself to
# a temporary directory on every launch and a directory bundle is far easier to
# inspect when somebody wants to know what is actually inside it.

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
# Widgets only. No QML runtime, no web engine, no network stack: the application
# has no use for any of them, and shipping a browser inside a review tool would
# be a large attack surface in exchange for nothing.
modules = Core,Gui,Widgets
plugins = platforms,styles,imageformats,iconengines,platformthemes

[android]
wheel_pyside =
wheel_shiboken =
plugins =

[nuitka]
macos.permissions =
mode = standalone
# --include-package-data is the line this whole file exists for; see above.
# --nofollow-import-to keeps the optional engine extras out of the bundle: the
# desktop reviews text and Markdown only, so a DOCX or PDF reader would be dead
# weight, and Flask has no business inside a native application.
extra_args = --quiet --noinclude-qt-translations --include-package=plainspeak --include-package-data=plainspeak --nofollow-import-to=flask --nofollow-import-to=docx --nofollow-import-to=pypdf --nofollow-import-to=pytest --company-name=PlainSpeak --product-name=PlainSpeak --file-description=PlainSpeak-desktop-review

[buildozer]
mode = debug
recipe_dir =
jars_dir =
ndk_path =
sdk_path =
