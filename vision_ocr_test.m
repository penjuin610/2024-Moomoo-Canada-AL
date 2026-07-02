#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <Vision/Vision.h>

static CGImageRef LoadCGImage(NSString *path) {
    NSImage *image = [[NSImage alloc] initWithContentsOfFile:path];
    if (!image) return nil;
    NSRect rect = NSMakeRect(0, 0, image.size.width, image.size.height);
    return [image CGImageForProposedRect:&rect context:nil hints:nil];
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) {
            fprintf(stderr, "usage: vision_ocr_test /path/to/image\n");
            return 1;
        }

        NSString *path = [NSString stringWithUTF8String:argv[1]];
        CGImageRef cgImage = LoadCGImage(path);
        if (!cgImage) {
            fprintf(stderr, "failed to load image\n");
            return 2;
        }

        VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
        request.recognitionLevel = VNRequestTextRecognitionLevelAccurate;
        request.usesLanguageCorrection = NO;
        request.recognitionLanguages = @[ @"en-US" ];

        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc] initWithCGImage:cgImage options:@{}];
        NSError *error = nil;
        [handler performRequests:@[ request ] error:&error];
        if (error) {
            fprintf(stderr, "vision ocr failed: %s\n", error.localizedDescription.UTF8String);
            return 3;
        }

        NSMutableArray *lines = [NSMutableArray array];
        for (VNRecognizedTextObservation *obs in request.results) {
            VNRecognizedText *candidate = [[obs topCandidates:1] firstObject];
            if (candidate) {
                [lines addObject:candidate.string];
            }
        }

        NSDictionary *payload = @{
            @"lines": lines,
            @"text": [lines componentsJoinedByString:@"\n"]
        };
        NSData *jsonData = [NSJSONSerialization dataWithJSONObject:payload options:0 error:&error];
        if (error || !jsonData) {
            fprintf(stderr, "failed to encode JSON\n");
            return 4;
        }
        fwrite(jsonData.bytes, 1, jsonData.length, stdout);
    }
    return 0;
}
