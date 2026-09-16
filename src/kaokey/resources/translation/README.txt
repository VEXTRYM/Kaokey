Kaokey translations
===================

English is the source language and does not need a .qm file.
Compiled translations belong in this directory and use this name:

    kaokey_<language>.qm

Examples:

    kaokey_ru.qm
    kaokey_de.qm
    kaokey_ja.qm

Typical Qt workflow later:

1. Mark user-visible strings with QObject.tr(...) / self.tr(...).
2. Run pyside6-lupdate to create/update .ts files.
3. Translate the .ts file with Qt Linguist (or another TS editor).
4. Run pyside6-lrelease to compile .ts -> .qm.
5. Put the .qm file in this directory.

TranslationManager automatically discovers compiled .qm languages.
