{
    description = "Data offloading service" ;

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    };

    outputs = { self, nixpkgs, ... }:
        let

            data_offloading_service_overlay = final: prev: {
                data_offloading_service = final.callPackage ./default.nix { };
            };

            my_overlays = [ data_offloading_service_overlay ];

        in
            {

                overlays.default = nixpkgs.lib.composeManyExtensions my_overlays;

                nixosModules.data-offload-service = import ./module.nix;

            };
}