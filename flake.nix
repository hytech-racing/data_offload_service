{
    description = "Data offloading service" ;

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    };

    outputs = { self, nixpkgs, ... }:
        let
            pkgs = import nixpkgs {
                system = "x86_64-linux";
            };
        in
            {
                packages.x86_64-linux.data-offload-service = import ./default.nix { inherit pkgs; };
                packages.x86_64-linux.default = import ./default.nix { inherit pkgs; };

                nixosModules.data-offload-service = import ./module.nix;

                nixosConfigurations.mySystem = nixpkgs.lib.nixosSystem {
                    system = "x86_64-linux";
                    modules = [
                        self.nixosModules.data-offload-service
                    ];

                    config = {
                        data-offload-service.enable = true;
                    };
                };
            };
}