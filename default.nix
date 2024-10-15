{ pkgs }:

pkgs.python311Packages.buildPythonApplication rec {
    
    pname = "data_offload_service";
    version = "1.0.0";

    buildInputs = [ pkgs.python311Packages.psutil pkgs.python311Packages.tkinter ];

    propagatedBuildInputs = buildInputs;

    nativeBuildInputs = buildInputs;

    src = ./.;

}