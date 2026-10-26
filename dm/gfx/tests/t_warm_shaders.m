// Parallel library preparation must preserve shader identity/reflection and
// publish each key once; one worker remains available for comparison.
#include "../nvn/nvn_mtl.m"
uint64_t g_t0_ns;
int dm_guest_as_contains(uintptr_t address) { (void)address; return 0; }
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t g_mod[MAX_MOD]; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return bp_now(); }
static int checks, failed;
#define CHECK(want) do { checks++; if (!(want)) { fprintf(stderr, "line %d: %s\n", __LINE__, #want); failed++; } } while (0)

@interface WarmDevice : NSObject {
@public id<MTLDevice> device; id<MTLLibrary> library; _Atomic int active, peak, calls;
}
@end
@implementation WarmDevice
- (id)forwardingTargetForSelector:(SEL)selector { return device; }
- (id<MTLLibrary>)newLibraryWithData:(dispatch_data_t)data error:(NSError **)error {
    (void)data; (void)error;
    int n = atomic_fetch_add(&active, 1) + 1, old = atomic_load(&peak);
    while (old < n && !atomic_compare_exchange_weak(&peak, &old, n)) {}
    atomic_fetch_add(&calls, 1);
    usleep(1000);   // A gated file/library load makes overlap observable.
    atomic_fetch_sub(&active, 1);
    return library;
}
@end

int main(void) { @autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice(); NSError *error = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal; vertex float4 vs(uint i [[vertex_id]]) { return float4(float(i),0,0,1); }" options:nil error:&error];
    CHECK(lib != nil); if (!lib) return 1;
    WarmDevice *fake = [WarmDevice new]; fake->device = dev; fake->library = lib; g_dev = (id)fake;
    NSString *dir = [NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
    [NSFileManager.defaultManager createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
    g_msl_dir = dir;
    NSMutableDictionary *map = [NSMutableDictionary dictionary];
    for (int i = 0; i < 96; i++) {
        NSString *key = [NSString stringWithFormat:@"%016x", i + 1]; map[key] = @"vertex";
        NSDictionary *reflection = @{@"chain": @DMSH_CHAIN, @"route": @"B", @"entry": @"vs", @"bindings": @[], @"vertex_inputs": @[]};
        [[NSJSONSerialization dataWithJSONObject:reflection options:0 error:nil] writeToFile:[dir stringByAppendingPathComponent:[key stringByAppendingString:@"_b.json"]] atomically:YES];
        [@"library fixture" writeToFile:[dir stringByAppendingPathComponent:[key stringByAppendingString:@"_b.metallib"]] atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
    g_shmap = map;
    for (NSString *jobs in @[@"1", @"8"]) {
        setenv("DM_PSO_WARM_JOBS", jobs.UTF8String, 1);
        atomic_store(&fake->active, 0); atomic_store(&fake->peak, 0); atomic_store(&fake->calls, 0);
        g_warm_items = [NSMutableArray array]; atomic_store(&g_warm_ready, 0);
        NSMutableDictionary *loaded = [NSMutableDictionary dictionary];
        warm_all_shaders(loaded, map.count + 1);
        CHECK(loaded.count == 96); CHECK(g_warm_items.count == 96);
        CHECK(atomic_load(&fake->calls) == 96); CHECK(atomic_load(&fake->active) == 0);
        CHECK(jobs.intValue == 1 ? atomic_load(&fake->peak) == 1 : atomic_load(&fake->peak) > 1);
        NSMutableSet *published = [NSMutableSet set];
        for (WarmItem *item in g_warm_items) {
            CHECK(![published containsObject:item->key]); [published addObject:item->key];
            CHECK(item->kind == 0 && item->shader == loaded[item->key]);
            CHECK(item->shader->fn != nil && item->shader->rf.route_b && item->shader->stage == 0);
            CHECK([item->key isEqualToString:@(item->shader->key)]);
            CHECK(fn4_of(item->shader->fn) != nil);
        }
    }
    [NSFileManager.defaultManager removeItemAtPath:dir error:nil];
    printf("warm shaders: %d checks, %d failed\n", checks, failed);
    return failed != 0;
} }
