height = 60; 
side_length_global = 92.5;
corner_offset_global = 30;
abs_width_x = corner_offset_global * 2 + side_length_global;
abs_width_y = corner_offset_global * 2 + side_length_global;


module create_box_outline(sidewall_offset=0, cut_corner_offset=0, vertical_mod = 0, height_mod = height, radius = 1, radius2 = 0, leds = false){
    
    if(radius2 == 0){
        radius2 = radius;
    }
    
    edge_inset = corner_offset_global + cut_corner_offset;
    side_length = side_length_global + sidewall_offset;
    side_offset = side_length + edge_inset;
    point1 = [edge_inset,0,0];
    point2 = [0,edge_inset,0];
    point3 = [side_offset,0,0];
    point4 = [side_offset + edge_inset, edge_inset,0];
    point5 = [side_offset + edge_inset, side_offset ,0];
    point6 = [side_offset,side_offset + edge_inset,0];
    point7 = [edge_inset,side_offset + edge_inset,0];
    point8 = [0,side_offset,0];
    points = [ point1, point2, point3, point4, point5, point6, point7, point8 ];
    
    //dump_points(points); // Replace 10 and 20 with your desired values for edge_inset and side_offset
    translate([-(sidewall_offset + cut_corner_offset * 2)/2,-(sidewall_offset + cut_corner_offset * 2)/2,vertical_mod]) c3_outline(points,radius, radius2,height_mod);
    
    // Now we should echo the x max and y max lengths
    // We should also print the perimeter length
    // Calculating x_max and y_max
    //x_max = max([for (p = points) p[0]]);
    //y_max = max([for (p = points) p[1]]);

    // Calculating the perimeter and printing outline coordinates
    perimeter = 0;
    corner_lengths = 4 * sqrt(edge_inset * edge_inset + edge_inset * edge_inset);
    
    side_lengths = side_length * 4;
    
    full_length = corner_lengths + side_lengths;
    
    led_length = 7;
    max_num_leds = full_length / led_length;
    
    echo(str("Total box perimeter: ", full_length));
    if(leds){
        echo(str("Max number of LEDS: ", max_num_leds));
    }
    echo(points);
    
   
}

 
module c3_outline(points, radius, radius2, height ){
    

    hull(){
        translate([radius,radius,0]) translate(points[0]) cylinder(r1=radius,r2=radius2, h=height);
        translate([radius, radius,0]) translate(points[1]) cylinder(r1=radius,r2=radius2, h=height);
        translate([-radius, radius,0])translate(points[2]) cylinder(r1=radius,r2=radius2, h=height);
        translate([-radius, radius,0]) translate(points[3]) cylinder(r1=radius,r2=radius2, h=height);
        translate([-radius, -radius,0]) translate(points[4]) cylinder(r1=radius,r2=radius2, h=height);
        translate([-radius, -radius,0])translate(points[5]) cylinder(r1=radius,r2=radius2, h=height);
        translate([radius, -radius,0]) translate(points[6]) cylinder(r1=radius,r2=radius2, h=height);
        translate([radius, -radius,0]) translate(points[7]) cylinder(r1=radius,r2=radius2, h=height);
    }
}
module box_back_bowed(){
    
   
    radius = 1000;
    translate([abs_width_x/2,abs_width_y/2,0]) difference(){
        translate([0,0,-radius +2.7]) sphere(radius,$fn = 400);

        translate([0,0,-radius*2]) rotate([0,0,45]) cylinder(20, 155,155,$fn=4);
        translate([0,0,-radius*2]) rotate([0,0,45]) cylinder(2000, radius*2,radius*2,$fn=4);
        
    }
     
}
module box_back(){
    difference(){
        color("white") create_box_outline(sidewall_offset = -4,cut_corner_offset=0, vertical_mod = 0, height_mod = shell_thickness * 2, radius = .01, radius2 = .01);
        //#translate([abs_width_x/2,abs_width_y/2,902]) rotate([0,90,90]) sphere(900, $fn=600);
        //#translate([0,abs_width_y/2 -13,0]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        //#translate([0,abs_width_y + 5,-49]) rotate([90,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        translate([0,abs_width_y/2 -14,-12]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
    }
}

module bottom_glass_spacer(){
    echo("Kick off making the box: ")
    difference(){
        color("red") create_box_outline(height_mod=2);
        
        // Make a big cutout in the middle of the box
        echo("Make a big cutout for the spacer: ");

        create_box_outline(sidewall_offset = -11.0,cut_corner_offset=0, vertical_mod = 0, height_mod = 10);
        translate([0,abs_width_y/2 -14,0]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
         //#translate([0,abs_width_y/2 -14,-3]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        echo("bottom Mirror:")
        // Make the top lip for the mirror
        #create_box_outline(sidewall_offset = -12,cut_corner_offset=4, vertical_mod = 2, height_mod = 1, radius=5, radius2=1);

        
        }
}



module rounded_box(points, radius, height){
    hull(){
        for (p = points){
            translate(p) cylinder(r=radius, h=height);
        }
    }
}
front_plexi_inset = 3;
module full_box(){
    difference(){
        //make the box
        echo("Kick off making the box: ")

        color("blue") create_box_outline(height_mod=height);
        
        // Make a big cutout in the middle of the box
        echo("Make a big cutout in the middle of the box: ")

        create_box_outline(sidewall_offset = -8,cut_corner_offset=0, vertical_mod = 0, height_mod = 2 + height);
        
        echo("Top Mirror:")
        // Make the top lip for the mirror
        create_box_outline(sidewall_offset = -6.3,cut_corner_offset=0, vertical_mod = height - front_plexi_inset, height_mod = 5);
        
        
        // Make the bottom lip for the mirror
        //create_box_outline(sidewall_offset = -6,cut_corner_offset=0, vertical_mod = 0, height_mod = 4);
        // Make the MIDDLE lip for the LEDs
        echo("Middle lips for LEDs:");
        middle_lip_height = 12.5;
        create_box_outline(sidewall_offset = -5,cut_corner_offset=0, vertical_mod = ((height) /3 - middle_lip_height/2 - 4), height_mod = middle_lip_height, radius=2, radius2=1, leds = true);
        
        create_box_outline(sidewall_offset = -5,cut_corner_offset=0, vertical_mod = ((height) /3*2 - middle_lip_height/3 - 2) , height_mod = middle_lip_height, radius=2, radius2=1, leds = true);
        
        echo("Middle holes for LED's wiring:");

        translate([0,abs_width_y/2 -14,0]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -1.5,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        translate([0,abs_width_y + 5,-40]) rotate([90,0,0]) create_box_outline(sidewall_offset = -side_length_global -1.5,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        translate([0,abs_width_y + 5,-48]) rotate([90,0,0]) create_box_outline(sidewall_offset = -side_length_global -1.5,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        translate([0,abs_width_y + 5,-54]) rotate([90,0,0]) create_box_outline(sidewall_offset = -side_length_global -1.5,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        
        //create_box_outline(sidewall_offset = -4,cut_corner_offset=0, vertical_mod = 2, height_mod = 8, radius = 10, radius2 = 4);
        // Make a hole for the wiring on this prototype
        //echo("Make a hole for the wiring on this prototype");
        
        //#translate([0,abs_width_y,-49]) rotate([90,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
        //cube([10,10,85]);
    }
}
module dome(top_radius,top_height,top_shell_thickness){
    

    difference(){
        cylinder(h=top_height,r=top_radius);
        translate([0, 0, -1]) cylinder(h=top_height + 2, r=top_radius - top_shell_thickness);
        translate([-top_radius, -top_radius * 2, -1])cube([top_radius*2, top_radius * 2, top_height + top_radius]);
    }
}
module ball(top_radius,top_height,top_shell_thickness){
    

    difference(){
        translate([0,0,top_height]) sphere(r=top_radius);

        translate([0, 0, top_height]) sphere(r=top_radius - top_shell_thickness);
        translate([0, 0, -1]) cylinder(h=top_height + 2, r=top_radius - top_shell_thickness);
        translate([-top_radius,-top_radius * 2, 0])cube([top_radius*2, top_radius * 2, top_height + top_radius + 2]);
    }
}
module basic_cover(){
    $fn=100;
    top_radius=17.5;
    top_height = 35;
    top_shell_thickness = 3;
    dome(top_radius,top_height,top_shell_thickness);
    ball(top_radius,top_height,top_shell_thickness);
}
translate([abs_width_x/2,abs_width_y-2,0])basic_cover();

// Make the bottom lip for the mirror
echo("Make the bottom lip for the mirror");

module back_sphere_curve(){
    difference(){
        box_back_bowed();
        translate([0,abs_width_y/2 -14,-12]) rotate([0,0,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
    }
}

//back_sphere_curve();
//box_back();

full_box();
translate([0,0,1.5]) bottom_glass_spacer();

echo("The size of the cube is");
echo(abs_width_x);

//translate([-320,139,-148]) import("iowa_smol.stl");
//translate([0.1,100,3]) rotate([90, 0, 270]) text("Made in IOWA, 2024", size = 4);

translate([abs_width_x,abs_width_y/2 - 20,15]) rotate([90,0,90]) linear_extrude(file = "/Users/ameliawietting/dev/ftc/logo_40mm.dxf",  height = 3, center = true);

translate([152.8,abs_width_y/2 - 22,3]) rotate([90, 0, 90]) linear_extrude(1) text("C3 Robotics", size = 6, font="Liberation Sans");









