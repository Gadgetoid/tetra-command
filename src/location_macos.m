#import <CoreLocation/CoreLocation.h>
#import <Foundation/Foundation.h>

#include "location.h"
#include "paths.h"

// Macros, not statics: kCLLocationAccuracyKilometer is an extern const. The
// filter is for CLGeocoder, which Apple rate limits.
#define ACCURACY kCLLocationAccuracyKilometer
#define FILTER 2000.0

// MKReverseGeocodingRequest replaces CLGeocoder but is macOS 26 only.
#pragma clang diagnostic ignored "-Wdeprecated-declarations"

@interface TetraLocation : NSObject <CLLocationManagerDelegate>
@property(nonatomic, strong) CLLocationManager *manager;
@property(nonatomic, strong) CLGeocoder *geocoder;
@property(nonatomic, copy) NSString *path;
@property(nonatomic, assign) BOOL naming;
@end

@implementation TetraLocation

- (void)writeLat:(double)lat lon:(double)lon place:(NSString *)place {
    NSMutableDictionary *out = [NSMutableDictionary dictionary];
    out[@"lat"] = @(lat);
    out[@"lon"] = @(lon);
    out[@"at"] = @((long long)[[NSDate date] timeIntervalSince1970]);
    if (place) out[@"place"] = place;

    NSError *error = nil;
    NSData *json = [NSJSONSerialization dataWithJSONObject:out options:0 error:&error];
    if (!json) {
        NSLog(@"location: cannot encode %@", error);
        return;
    }
    if (![json writeToFile:self.path atomically:YES]) {
        NSLog(@"location: cannot write %@", self.path);
        return;
    }
    NSLog(@"location: %.4f,%.4f %@", lat, lon, place ?: @"(no place name yet)");
}

- (void)locationManager:(CLLocationManager *)manager
     didUpdateLocations:(NSArray<CLLocation *> *)locations {
    CLLocation *fix = locations.lastObject;
    if (!fix) return;

    // Written once, after the name: a run ending inside the geocode would
    // otherwise leave a fix with no place. One request at a time.
    if (self.naming) return;
    self.naming = YES;

    CLLocationCoordinate2D where = fix.coordinate;
    [self.geocoder reverseGeocodeLocation:fix completionHandler:
        ^(NSArray<CLPlacemark *> *marks, NSError *error) {
            self.naming = NO;
            CLPlacemark *mark = marks.firstObject;
            if (!mark) {
                NSLog(@"location: no place name: %@", error.localizedDescription);
            }
            NSString *place = mark ? (mark.locality ?: mark.subAdministrativeArea
                                                    ?: mark.name) : nil;
            [self writeLat:where.latitude lon:where.longitude place:place];
        }];
}

- (void)locationManager:(CLLocationManager *)manager didFailWithError:(NSError *)error {
    NSLog(@"location: %@", error.localizedDescription);
}

- (void)locationManagerDidChangeAuthorization:(CLLocationManager *)manager {
    switch (manager.authorizationStatus) {
        // macOS has no AuthorizedWhenInUse; the request lands on Always.
        case kCLAuthorizationStatusAuthorizedAlways:
            [manager startUpdatingLocation];
            break;
        case kCLAuthorizationStatusDenied:
        case kCLAuthorizationStatusRestricted:
            NSLog(@"location: denied. System Settings > Privacy & Security >");
            NSLog(@"          Location Services, then allow Tetra Command.");
            NSLog(@"          Until then, name a place: fetch_weather.py \"Cambridge\"");
            break;
        default:
            break;
    }
}

@end

static TetraLocation *watcher = nil;

void location_start(const char *data) {
    if (watcher) return;

    // No Info.plist means no usage string, so the prompt never appears.
    if (!paths_bundled()) {
        NSLog(@"location: not bundled, so no Location Services. Run make bundle,");
        NSLog(@"          or name a place: fetch_weather.py \"Cambridge\"");
        return;
    }

    watcher = [[TetraLocation alloc] init];
    watcher.path = [NSString stringWithFormat:@"%s/location.json", data];
    watcher.geocoder = [[CLGeocoder alloc] init];
    watcher.manager = [[CLLocationManager alloc] init];
    watcher.manager.delegate = watcher;
    watcher.manager.desiredAccuracy = ACCURACY;
    watcher.manager.distanceFilter = FILTER;
    [watcher.manager requestWhenInUseAuthorization];
}

void location_stop(void) {
    [watcher.manager stopUpdatingLocation];
    watcher = nil;
}
