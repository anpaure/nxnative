// Installed DLC enumeration must return all entries, including pages past 64.
#include "../hle_misc.c"
#include <sys/stat.h>
#include <unistd.h>

void *guest_sym(const char *name) { (void)name; return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
void hle_bind_system_event(void *g, int autoclear) { (void)g; (void)autoclear; }
__asm__(".text\n.p2align 2\n.globl _dm_bigstack_enter\n_dm_bigstack_enter:\n    br x16\n");
static int checks, fails;
#define CHECK(c, msg) do { checks++; if (!(c)) { fails++; fprintf(stderr, "FAIL: %s\n", msg); } } while (0)

int main(void) {
    char dir[] = "build/aoc-XXXXXX", path[256];
    if (!mkdtemp(dir)) { perror("mkdtemp"); return 1; }
    // Sparse, reverse-created indices: check sorting and pagination, not just count.
    for (int i = 99; i >= 1; i--) {
        snprintf(path, sizeof path, "%s/%d", dir, i * 2);
        if (mkdir(path, 0700)) { perror("mkdir"); return 1; }
    }
    setenv("DM_AOC_DIR", dir, 1); unsetenv("DM_AOC_OWNED");
    CHECK(h_aoc_Count() == 99, "all 99 installed DLC entries counted");
    int out[100]; for (int i = 0; i < 100; i++) out[i] = -1;
    CHECK(h_aoc_List(out, 0, 100) == 99, "full list returns 99 entries");
    int ordered = 1; for (int i = 0; i < 99; i++) ordered &= out[i] == (i + 1) * 2;
    CHECK(ordered && out[99] == -1, "all indices sorted; buffer tail untouched");
    CHECK(h_aoc_List(out, 64, 7) == 7 && out[0] == 130 && out[6] == 142, "page beyond old 64-entry limit");
    CHECK(h_aoc_List(out, 95, 10) == 4 && out[3] == 198, "last page reports only remaining entries");
    CHECK(h_aoc_List(out, 99, 10) == 0, "page at end is empty");
    setenv("DM_AOC_OWNED", "0", 1); g_naoc = -1;
    CHECK(h_aoc_Count() == 0 && h_aoc_List(out, 0, 10) == 0, "DLC-off switch still reports none");
    unsetenv("DM_AOC_OWNED"); unsetenv("DM_AOC_DIR"); g_naoc = -1;
    CHECK(h_aoc_Count() == 0, "no DLC directory reports none");
    for (int i = 1; i <= 99; i++) { snprintf(path, sizeof path, "%s/%d", dir, i * 2); rmdir(path); }
    rmdir(dir);
    printf("aoc: %d checks, %d failed\n", checks, fails);
    return fails != 0;
}
