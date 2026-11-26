// GreenPi sensor radiation shield ("Stevenson-style" louvred stack)
// for one SparkFun-style 1" x 1" Qwiic sensor board (SHTC3, BME688, SHT45...).
//
// Sun on a bare sensor makes it read 10-20 F high. The stacked rings shade
// the board while letting air move through. All parts print flat with no
// supports: print the rings and the cap TOP-SIDE DOWN.
//
// Hardware: 3x M4 threaded rod (length = stack height + ~15 mm), 6x M4 nut,
//           2x M2.5x6 screw for the board, 2x wood/masonry screw for the wall.
// Material: WHITE ASA or PETG (white reflects sun; PLA softens in a hot
//           greenhouse). If printed in grey/black, paint it white.
//
// Render a part:  openscad -D 'part="ring"' -o ring.stl sensor_shield.scad
// parts: "assembly", "exploded", "cap", "ring", "sled"

part   = "assembly";
rings  = 5;      // louvre rings below the cap: 5 outside, 3 inside the greenhouse

od     = 110;    // ring outer diameter
id     = 56;     // ring inner opening (air + cable path)
t      = 2;      // ring / cap thickness
skirt  = 7;      // downward, outward-flared lip (blocks low sun)
flare  = 5;      // how far the lip flares out (35 deg: prints without support)
skirt_t= 1.6;
pitch  = 21;     // ring-to-ring spacing (top to top); leaves ~12 mm air slots
rod_r  = 45;     // radius of the three rods
rod_d  = 4.5;    // clearance for M4 rod
boss_d = 9;      // spacer tube diameter

board  = 25.4;   // Qwiic board is 1.0" square
hole_sp= 20.32;  // its mounting holes are 0.8" apart (check your board!)
arm_len= 70;     // wall stand-off from cap edge

$fn = 96;

module rod_holes(h) {
    for (a = [90, 210, 330]) rotate(a) translate([rod_r, 0, -1])
        cylinder(d = rod_d, h = h + 2, $fn = 24);
}

// Lip hanging from the outer edge, flaring outward as it goes down.
module flared_skirt(d) {
    translate([0, 0, -t - skirt]) difference() {
        cylinder(d1 = d + 2 * flare, d2 = d, h = skirt + 0.01);
        translate([0, 0, -0.01])
            cylinder(d1 = d + 2 * flare - 2 * skirt_t, d2 = d - 2 * skirt_t, h = skirt + 0.03);
    }
}

// One louvre ring, modelled the way it hangs (skirt and spacers point down).
module ring() {
    difference() {
        union() {
            translate([0, 0, -t]) difference() {
                cylinder(d = od, h = t);
                translate([0, 0, -1]) cylinder(d = id, h = t + 2);
            }
            flared_skirt(od);
            // spacer tubes: they sit on the ring below
            for (a = [90, 210, 330]) rotate(a) translate([rod_r, 0, -pitch])
                cylinder(d = boss_d, h = pitch - t, $fn = 32);
        }
        translate([0, 0, -pitch - 1]) rod_holes(pitch + 4);
    }
}

// Solid top cap with wall arm; the sensor sled clips under its centre.
module cap() {
    difference() {
        union() {
            translate([0, 0, -t]) cylinder(d = od + 4, h = t + 1);
            flared_skirt(od + 4);
            for (a = [90, 210, 330]) rotate(a) translate([rod_r, 0, -pitch])
                cylinder(d = boss_d, h = pitch - t, $fn = 32);
            // centre socket for the sled
            translate([0, 0, -t - 6]) cylinder(d = 16, h = 6);
            // wall arm (lies flat on the bed when the cap prints top-down)
            translate([od / 2 - 5, -10, -t]) cube([arm_len + 5, 20, t + 1]);
            translate([od / 2 - 5, -1.5, -t - 12]) cube([arm_len + 5, 3, 12]);   // stiffening rib
            // wall plate
            translate([od / 2 + arm_len - 4, -25, -t - 40]) cube([4, 50, 41]);
        }
        translate([0, 0, -pitch - 1]) rod_holes(pitch + 4);
        // sled slot
        translate([-6.2, -1.7, -t - 7]) cube([12.4, 3.4, 7]);
        // wall screw holes + zip-tie slots for the QwiicBus board / cable
        for (z = [-t - 10, -t - 32]) translate([od / 2 + arm_len - 6, 0, z])
            rotate([0, 90, 0]) cylinder(d = 4.5, h = 10, $fn = 24);
        for (y = [-18, 18]) translate([od / 2 + arm_len - 6, y - 2, -t - 24])
            cube([10, 4, 2.5]);
        for (x = [od / 2 + 15, od / 2 + 40]) translate([x, -12, -t - 1]) cube([3, 24, t + 3]);
    }
}

// Sensor sled: a tongue that plugs into the cap, holding the board upright
// in the middle of the stack, sensor chip facing out into the airflow.
module sled() {
    drop = (floor(rings / 2) + 1) * pitch;   // board hangs mid-stack
    // tongue
    translate([-6, -1.5, -7]) cube([12, 3, 7 + 1]);
    // stem
    translate([-4, -1.5, -drop + board / 2]) cube([8, 3, drop - board / 2 - 6]);
    // board plate with two standoffs
    translate([0, 0, -drop]) difference() {
        union() {
            translate([-board / 2, -1.5, -board / 2]) cube([board, 3, board]);
            for (x = [-hole_sp / 2, hole_sp / 2]) translate([x, -1.5, hole_sp / 2])
                rotate([90, 0, 0]) cylinder(d = 5.5, h = 3, $fn = 24);
        }
        for (x = [-hole_sp / 2, hole_sp / 2]) translate([x, 5, hole_sp / 2])
            rotate([90, 0, 0]) cylinder(d = 2.2, h = 12, $fn = 16);   // M2.5 self-tap
        // window behind the sensor so air reaches both sides
        translate([-7, -3, -9]) cube([14, 6, 12]);
    }
}

module board_ghost() {
    drop = (floor(rings / 2) + 1) * pitch;
    color("red", 0.9) translate([-board / 2, -6.1, -drop - board / 2]) cube([board, 1.6, board]);
    color([0.15, 0.15, 0.15]) translate([-4, -7.2, -drop - 2]) cube([8, 1.2, 4]);   // Qwiic plug
}

module assembly(gap = 0) {
    color("white") cap();
    color([0.85, 0.85, 0.85]) translate([0, 0, gap > 0 ? -gap * 0.6 : 0]) sled();
    if (gap == 0) board_ghost();
    for (i = [1 : rings]) color(i % 2 ? [0.96, 0.96, 0.96] : [0.9, 0.9, 0.9])
        translate([0, 0, -i * pitch - i * gap]) ring();
    // rods
    if (gap == 0) color([0.55, 0.55, 0.6]) for (a = [90, 210, 330]) rotate(a)
        translate([rod_r, 0, -(rings + 1) * pitch]) cylinder(d = 4, h = (rings + 1) * pitch + 6, $fn = 16);
}

if (part == "assembly") assembly();
else if (part == "cutaway") difference() {
    assembly();
    translate([0, -200, -300]) cube([200, 200, 400]);   // remove the front-right quarter
}
else if (part == "exploded") assembly(gap = 22);
else if (part == "cap") rotate([180, 0, 0]) cap();       // print top-side down
else if (part == "ring") rotate([180, 0, 0]) ring();     // print top-side down
else if (part == "sled") rotate([90, 0, 0]) sled();      // print lying flat
