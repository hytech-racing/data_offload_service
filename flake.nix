{
    description = "Data offloading service" ;

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    };

    outputs = { self, nixpkgs, ... }:
        let

            pkgs = import nixpkgs { system = "x86_64-linux"; }; # for testing purposes

            data_offloading_service_overlay = final: prev: {
                data_offloading_service = final.callPackage ./default.nix { };
            };

            my_overlays = [ data_offloading_service_overlay ];

        in
            {

                overlays.default = nixpkgs.lib.composeManyExtensions my_overlays;

                packages.x86_64-linux.data-offload-service = import ./default.nix { inherit pkgs; }; # for testing purposes
                packages.x86_64-linux.default = import ./default.nix { inherit pkgs; }; # for testing purposes

                nixosModules.data-offload-service = { config, pkgs, ... }:
                {

                    config =  {

                        systemd.services.data-offload-service = {
                            description = "Data Offload Service";
                            wantedBy = [ "multi-user.target" ];
                            after = [ "network.target" ];
                            environment =  {
                                DISPLAY=":0";
                                XAUTHORITY="/run/user/1000/.mutter-Xwaylandauth.ZIBAV2";
                            serviceConfig = {
                                After = [ "network.target" ];
                                ExecStart = "${pkgs.data_offloading_service}/bin/offload.py";
                                Restart = "always";
                            };
                        };

                    };

                };

            };
}