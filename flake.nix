{
    description = "Data offloading service" ;

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
        mcap.url = "github:KrishKittur/py_mcap_nix";
    };

    outputs = { self, nixpkgs, mcap, ... }:
        let

            data_offloading_service_overlay = final: prev: {
                data_offloading_service = final.callPackage ./default.nix { };
            };

            my_overlays = [ data_offloading_service_overlay mcap.overlays.default ];

            pkgs = import nixpkgs {
                overlays = my_overlays;
                system = "x86_64-linux"; 
            };

        in
            {

                overlays.default = nixpkgs.lib.composeManyExtensions my_overlays;

                packages.x86_64-linux.data-offload-service = pkgs.data_offloading_service; # for testing purposes
                packages.x86_64-linux.default = pkgs.data_offloading_service; # for testing purposes

                packages.aarch64-darwin.data-offload-service = pkgs.data_offloading_service; # for testing purposes
                packages.aarch64-darwin.default = pkgs.data_offloading_service; # for testing purposes

                nixosModules.data-offload-service = { config, pkgs, ... }:
                {

                    config =  {
                        
                        systemd.user.services.data-offload-service = {
                            description = "Data Offload Service";
                            # wantedBy = [ "multi-user.target" ];
                            wantedBy = [ "default.target" ];
                            after = [ "network.target" ];
                            # preStart = ''
                            #     AUTH_FILE=$(find /run/user/1000 -name ".mutter-Xwaylandauth.*" | head -n 1)
                            #     if [ -z "$AUTH_FILE" ]; then
                            #         echo "WAYLAND_AUTH_PATH not found!" >&2
                            #         exit 1
                            #     fiz
                            #     export XAUTHORITY=$AUTH_FILE
                            # '';
                            environment =  {
                                DISPLAY=":0";
                                # XAUTHORITY="$XAUTHORITY";
                            };
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