/* Lanciatore di GM Journal per Windows: GMJournal.exe.
 *
 * Carica Python incorporato (cartella «runtime») e avvia app\run.py. Non apre nessuna finestra del terminale.
 * Se Python non si carica (file mancanti, sistema troppo vecchio) mostra un messaggio chiaro invece di non fare niente.
 *
 * Costruzione (da Linux): vedi build_package.py.
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

#define PYTHON_DLL L"python313.dll"
#define PATH_MAX_CHARS 32768

typedef int (*PyMainFn)(int, wchar_t **);

static void fail(const wchar_t *what, DWORD code)
{
    wchar_t text[1024];
    swprintf(text, 1024,
             L"GM Journal non riesce a partire.\n\n%ls\n(codice Windows %lu)\n\n"
             L"Prova a reinstallare il programma. Se il problema resta, scrivi a chi te lo ha dato "
             L"riportando questo messaggio.",
             what, (unsigned long)code);
    MessageBoxW(NULL, text, L"GM Journal", MB_OK | MB_ICONERROR);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show)
{
    (void)inst; (void)prev; (void)cmd; (void)show;

    static wchar_t exe[PATH_MAX_CHARS], home[PATH_MAX_CHARS], runtime[PATH_MAX_CHARS];
    static wchar_t dll[PATH_MAX_CHARS], script[PATH_MAX_CHARS];

    DWORD n = GetModuleFileNameW(NULL, exe, PATH_MAX_CHARS);
    if (n == 0 || n >= PATH_MAX_CHARS) { fail(L"Percorso del programma non leggibile.", GetLastError()); return 1; }

    wcscpy(home, exe);
    wchar_t *slash = wcsrchr(home, L'\\');
    if (!slash) { fail(L"Percorso del programma non valido.", 0); return 1; }
    *slash = L'\0';

    swprintf(runtime, PATH_MAX_CHARS, L"%ls\\runtime", home);
    swprintf(dll, PATH_MAX_CHARS, L"%ls\\" PYTHON_DLL, runtime);
    swprintf(script, PATH_MAX_CHARS, L"%ls\\app\\run.py", home);

    SetDllDirectoryW(runtime);
    HMODULE python = LoadLibraryExW(dll, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!python) { fail(L"Non riesco a caricare Python (cartella «runtime»).", GetLastError()); return 1; }

    PyMainFn py_main = (PyMainFn)GetProcAddress(python, "Py_Main");
    if (!py_main) { fail(L"La copia di Python non e' valida.", GetLastError()); return 1; }

    /* -I: ignora variabili d'ambiente e cartelle dell'utente, cosi' il programma gira sempre allo stesso modo. */
    wchar_t *args[] = { exe, L"-I", L"-X", L"utf8", script, NULL };
    return py_main(5, args);
}
