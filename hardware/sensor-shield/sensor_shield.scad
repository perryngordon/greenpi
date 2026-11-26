// GreenPi sensor radiation shield, v2 (wind + snow + QwiicBus extender)
//
// A stack of nested 45-degree cone louvres for one SparkFun-style 1" x 1"
// Qwiic sensor board (BME688, SHTC3, SHT45...) plus the SparkFun QwiicBus
// EndPoint, so the Ethernet run plugs straight into the shield.
//
//  * Sun: louvres shade the sensor (bare sensors read 10-20 F high in sun).
//  * Snow: 45-degree slopes shed snow; each cone overlaps the next so there is
//    no straight path in (blown snow must climb ~40 mm uphill); the bottom
//    ring has a floor so gusts can't blow snow up the middle; drain holes let
//    anything that melts inside run out.
//  * Wind (Ward gusts 100+ mph): ribbed arm, 4-screw wall plate, spacer tubes
//    cut to the cone slope so every joint is a full face, sled cross-bolted.
//  * Extender: EndPoint on the back of the sled near the top, RJ45 pointing
//    DOWN (no water into the jack); the cable comes up through the floor hole
//    directly below it; zip-tie tab under the jack takes the cable's weight.
//    Sensor on the front of the sled, mid-stack, joined by a short Qwiic cable.
//
// Everything prints without supports (45-degree overhangs). Print the cap,
// rings and bottom ring as exported (narrow / flat side down); sled flat.
//
// parts: "assembly", "cutaway", "exploded", "cap", "ring", "bottom", "sled"

part   = "assembly";
rings  = 5;      // louvres incl. the bottom one: 5 outside, 4 inside (>= 4 fits the extender)

r_in   = 30;     // inner opening radius (60 mm column for the sled)
r_out  = 58;     // louvre outer radius
r_cap  = 62;     // cap overhangs the louvres a little
tn     = 2.4;    // wall thickness, normal to the 45-degree surface
tv     = tn * sqrt(2);   // same, measured vertically
pitch  = 21;     // louvre spacing; ~12 mm air channels between cones

rod_r  = 46;     // three M4 rods on this radius
rod_d  = 4.5;
boss_d = 10;     // spacer tubes
nut_d  = 12;     // flat nut seats

wall_x = r_cap + 45;   // wall plate distance from the centre

// sled: plate in the XZ plane, centred at y = sy so the boards on both
// faces balance inside the 60 mm column
sy      = -6;
plate_t = 4;
spacer  = 5;     // M2.5 nylon spacers under each board
hole    = 2.7;   // M2.5 clearance
qhole   = 20.32; // Qwiic 1" board hole spacing (check yours)

// SparkFun QwiicBus EndPoint (from SparkFun's Eagle file): 44.45 x 25.4 mm,
// holes on a 20.32 mm square at one end, RJ45 at the other end.
ep_len  = 44.45;
ep_w    = 25.4;
ep_top  = -tv - 14;                    // top edge of the EndPoint board
ep_bot  = ep_top - ep_len;             // RJ45 end
ep_hole_z = [ep_top - 2.54, ep_top - 22.86];
jack_h  = 13.5;                        // RJ45 height above the board
plug_end = ep_bot - 11;                // where the RJ45 plug ends
jack_y  = sy + plate_t / 2 + spacer + 1.6 + jack_h / 2;

sens_z  = min(-(rings * pitch) / 2 - 8, -57);   // sensor board centre
tab_z   = plug_end - 6;                          // zip-tie tab (top face)

$fn = 120;

// ---------- louvre geometry ----------

module cone_shell(ro) {
    rotate_extrude() polygon([[r_in, 0], [ro, -(ro - r_in)],
                              [ro, -(ro - r_in) - tv], [r_in, -tv]]);
}

// Everything below this louvre's top surface (used to trim spacer tubes).
module below_top() {
    rotate_extrude() polygon([[0, 0], [r_in, 0], [300, -(300 - r_in)],
                              [300, -600], [0, -600]]);
}

module at_rods() { for (a = [90, 210, 330]) rotate(a) translate([rod_r, 0, 0]) children(); }

module rod_holes() { at_rods() translate([0, 0, -300]) cylinder(d = rod_d, h = 400, $fn = 24); }

// Spacer tubes from this louvre down to the next one; both ends follow the
// cone surfaces so the joints are full faces.
module tubes() {
    difference() {
        intersection() {
            at_rods() translate([0, 0, -pitch - 40]) cylinder(d = boss_d, h = pitch + 50, $fn = 40);
            below_top();
        }
        translate([0, 0, -pitch]) below_top();
    }
}

module ring() {
    difference() {
        union() { cone_shell(r_out); tubes(); }
        rod_holes();
    }
}

// Bottom louvre: floor with cable hole + drain holes, flat nut seats below.
module bottom() {
    difference() {
        union() {
            cone_shell(r_out);
            translate([0, 0, -tv]) cylinder(r = r_in + tn, h = tv);
            intersection() {
                at_rods() translate([0, 0, -(rod_r - r_in) - tv - 6])
                    cylinder(d = nut_d, h = 40, $fn = 40);
                below_top();
            }
        }
        rod_holes();
        translate([0, jack_y, -20]) cylinder(d = 22, h = 40);               // Ethernet cable
        for (a = [30 : 60 : 330]) rotate(a) translate([23, 0, -20])
            cylinder(d = 5, h = 40, $fn = 24);                              // drains
    }
}

// Cap: solid roof + louvre, wall arm, socket for the sled.
module cap() {
    difference() {
        union() {
            cone_shell(r_cap);
            translate([0, 0, -tv]) cylinder(r = r_in + tn, h = tv);
            tubes();
            at_rods() translate([0, 0, -(rod_r - r_in) - tv])               // flat nut seats on top
                cylinder(d = nut_d, h = (rod_r - r_in) + tv, $fn = 40);
            translate([0, 0, -tv - 12]) cylinder(d = 20, h = 12.1);          // sled socket
            // arm: flange flush with the top, deep rib that hugs the roof
            translate([20, -10, -5]) cube([wall_x - 20, 20, 5]);
            rotate([90, 0, 0]) linear_extrude(height = 6, center = true)
                polygon([[r_in - 1, 0], [wall_x, 0], [wall_x, -45], [r_cap + 4, -45],
                         [r_cap + 1, -(r_cap - r_in) - 1.5], [r_in - 1, -1.5]]);   // sinks 1.5 mm into the roof
            // wall plate
            translate([wall_x - 5, -30, -60]) cube([5, 60, 60]);
        }
        rod_holes();
        translate([-6.2, sy - plate_t / 2 - 0.2, -tv - 12.5]) cube([12.4, plate_t + 0.4, 12.5]);
        translate([0, 30, -tv - 6]) rotate([90, 0, 0]) cylinder(d = 3.3, h = 60, $fn = 24);  // M3 cross-bolt
        for (y = [-20, 20], z = [-12, -48]) translate([wall_x - 10, y, z])
            rotate([0, 90, 0]) cylinder(d = 4.8, h = 20, $fn = 24);          // wall screws
        for (y = [-6, 6]) translate([wall_x - 10, y - 2, -40]) cube([20, 4, 3]);   // cable zip-tie
    }
}

// ---------- sled ----------

module sled() {
    difference() {
        union() {
            // tongue into the cap socket
            translate([-6, sy - plate_t / 2, -tv - 12.2]) cube([12, plate_t, 12]);
            // plate
            translate([-13.5, sy - plate_t / 2, tab_z - 3]) cube([27, plate_t, -tv - 12.2 - tab_z + 3]);
            // zip-tie tab under the RJ45 plug (cable is tied to its edge)
            translate([-11, sy, tab_z - 3]) cube([22, jack_y - 4 - sy, 3]);
        }
        // cross-bolt
        translate([0, 20, -tv - 6]) rotate([90, 0, 0]) cylinder(d = 3.3, h = 40, $fn = 24);
        // EndPoint holes (back face)
        for (x = [-10.16, 10.16], z = ep_hole_z) translate([x, 20, z])
            rotate([90, 0, 0]) cylinder(d = hole, h = 40, $fn = 20);
        // sensor holes (front face)
        for (x = [-qhole / 2, qhole / 2], z = [sens_z - qhole / 2, sens_z + qhole / 2])
            translate([x, 20, z]) rotate([90, 0, 0]) cylinder(d = hole, h = 40, $fn = 20);
        // air window behind the sensor chip
        translate([-6, sy - 5, sens_z - 6]) cube([12, 10, 12]);
        // zip-tie slots
        for (x = [-7, 7]) translate([x - 1.5, jack_y - 9, tab_z - 5]) cube([3, 2.5, 8]);
    }
}

// ---------- non-printed parts (for pictures) ----------

module ghosts() {
    yb = sy + plate_t / 2 + spacer;            // EndPoint board back
    color([0.8, 0.1, 0.1]) translate([-ep_w / 2, yb, ep_bot]) cube([ep_w, 1.6, ep_len]);
    color([0.75, 0.75, 0.7]) translate([-7.6, yb + 1.6, ep_bot]) cube([15.2, jack_h, 16]);
    color([0.9, 0.9, 0.95]) translate([-6, jack_y - 5.5, plug_end]) cube([12, 11, 11]);
    color([0.2, 0.35, 0.8]) translate([0, jack_y, -rings * pitch - 40])
        cylinder(d = 5, h = plug_end + rings * pitch + 40, $fn = 20);        // Ethernet cable
    yf = sy - plate_t / 2 - spacer;            // sensor board back
    color([0.8, 0.1, 0.1]) translate([-12.7, yf - 1.6, sens_z - 12.7]) cube([25.4, 1.6, 25.4]);
    color([0.1, 0.1, 0.1]) translate([-2, yf - 2.6, sens_z - 2]) cube([4, 1, 4]);   // sensor chip
}

module rods() {
    color([0.55, 0.55, 0.6]) at_rods()
        translate([0, 0, -rings * pitch - 30]) cylinder(d = 4, h = rings * pitch + 36, $fn = 16);
}

module assembly(gap = 0) {
    color("white") cap();
    translate([0, 0, gap > 0 ? -gap * 0.4 : 0]) {
        color([0.85, 0.85, 0.85]) sled();
        if (gap == 0) ghosts();
    }
    for (i = [1 : rings]) translate([0, 0, -i * pitch - i * gap])
        color(i % 2 ? [0.95, 0.95, 0.95] : [0.88, 0.88, 0.88])
            if (i == rings) bottom(); else ring();
    if (gap == 0) rods();
}

if (part == "assembly") assembly();
else if (part == "cutaway") difference() {
    assembly();
    translate([0, -300, -400]) cube([300, 300, 500]);   // remove the front-right quarter
}
else if (part == "section") difference() {               // side view through the centre
    assembly();
    translate([-300, -300, -400]) cube([300, 600, 500]);
}
else if (part == "exploded") assembly(gap = 30);
else if (part == "cap")    rotate([180, 0, 0]) cap();      // print roof-down
else if (part == "ring")   rotate([180, 0, 0]) ring();     // print narrow end down
else if (part == "bottom") rotate([180, 0, 0]) bottom();   // print floor-down
else if (part == "sled")   rotate([90, 0, 0]) sled();      // print flat, tab up
