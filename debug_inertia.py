import math

target_I = 0.00004137
tolerance = 0.000001
# Formula inputs: Rebar Diameter, Column Diameter, Thickness, Cover
rebar_diameters = [10, 12, 14, 16, 18, 20, 22, 25, 28, 32, 36, 40]
column_diameters = [200, 300, 400, 500, 600, 800, 1000]
thicknesses = [10, 12, 14, 16, 20]
covers = [35] # From code hardcode

print(f"Searching for I = {target_I} (m^4) +/- {tolerance}")

for D in column_diameters:
    for t in thicknesses:
        for d_bar in rebar_diameters:
            # Code logic matches:
            # rebar_distance_mm = (diameter / 2) - thickness - 35 - (rebar_diameter / 2)
            dist = (D / 2) - t - 35 - (d_bar / 2)
            
            if dist <= 0: continue

            I_self = (math.pi * d_bar**4) / 64
            A_one = (math.pi * d_bar**2) / 4
            
            # Formula: 8*Is + 4*As*dist^2
            I_total_mm4 = 8 * I_self + 4 * A_one * dist**2
            I_total_m4 = I_total_mm4 * 1e-12
            
            if abs(I_total_m4 - target_I) < tolerance or abs(I_total_m4 - target_I)/target_I < 0.05:
                print(f"MATCH FOUND! D={D}, t={t}, d_bar={d_bar}")
                print(f"  Dist: {dist} mm")
                print(f"  I_calc: {I_total_m4:.8f}")

            # Also check if user might be using Fixed Cover "a" instead of calculating it?
            # Say 'a' is just distance from center? No, user formula says (R-a).
            # If user meant R as Outer and a as edge cover?
            # Let's try direct distance loop
            
print("\nChecking common distances directly...")
for d_bar in rebar_diameters:
    I_self = (math.pi * d_bar**4) / 64
    A_one = (math.pi * d_bar**2) / 4
    
    # Solve for dist
    # I_target_mm4 = 41370000
    # 41370000 = 8*Is + 4*As*dist^2
    # 4*As*dist^2 = 41370000 - 8*Is
    # dist = sqrt( (41370000 - 8*Is) / (4*As) )
    
    target_mm4 = target_I * 1e12
    numerator = target_mm4 - 8 * I_self
    if numerator > 0:
        calc_dist = math.sqrt(numerator / (4 * A_one))
        print(f"For d_bar={d_bar}mm, required dist from center = {calc_dist:.1f} mm")
        # Reverse engineer D
        # dist = R_outer - t - 35 - d/2
        # R_outer = dist + t + 35 + d/2
        # D = 2 * R_outer (assuming t=10)
        D_est = 2 * (calc_dist + 10 + 35 + d_bar/2)
        print(f"  -> Implies D approx {D_est:.1f} mm (with t=10, cover=35)")
