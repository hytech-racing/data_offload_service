{ python311Packages, py_mcap_pkg, mcap-cli }:

python311Packages.buildPythonApplication rec {

  pname = "data_offload_service";
  version = "1.0.0";

  buildInputs = [
    python311Packages.psutil
    python311Packages.tkinter
    python311Packages.requests
    python311Packages.lz4
    python311Packages.zstandard
    python311Packages.setuptools
    py_mcap_pkg
    mcap-cli
  ];

  propagatedBuildInputs = buildInputs;
  nativeBuildInputs =  buildInputs;

  src = builtins.path { path = ./.; name = "source"; };
}