height = 40; 
side_length_global = 80;
corner_offset_global = 20;
abs_width_x = corner_offset_global * 2 + side_length_global;
abs_width_y = corner_offset_global * 2 + side_length_global;

module create_box_outline(sidewall_offset=0, cut_corner_offset=0, vertical_mod = 0, height_mod = height, radius = 1, radius2 = 0){
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
    translate([-(sidewall_offset + cut_corner_offset * 2)/2,-(sidewall_offset + cut_corner_offset * 2)/2,vertical_mod]) c3_outline(points,radius, radius2,height_mod);
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

difference(){
    //make the box
    color("blue") create_box_outline(mod_height=height);
    // Make a big cutout in the middle of the box
    create_box_outline(sidewall_offset = -10,cut_corner_offset=0, vertical_mod = 2, height_mod = 2 + height);
    // Make the top lip for the mirror
    create_box_outline(sidewall_offset = -6,cut_corner_offset=0, vertical_mod = height - 4, height_mod = 5);
    // Make the bottom lip for the mirror
    create_box_outline(sidewall_offset = -4,cut_corner_offset=0, vertical_mod = 2, height_mod = 8, radius = 10, radius2 = 1);
    // Make a hole for the wiring on this prototype
    translate([0,abs_width_y/2 - 9,0]) create_box_outline(sidewall_offset = -side_length_global -2,cut_corner_offset=-corner_offset_global/2 - 2, vertical_mod = -2, height_mod = height - 10, radius=3, radius2=1);
    //cube([10,10,85]);
}

echo("The size of the cube is");
echo(abs_width_x);