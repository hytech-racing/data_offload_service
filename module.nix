{ config, pkgs, ... }:

{
    options.data_offload_service.enable = pkgs.lib.mkOption {
        type = pkgs.lib.types.bool;
        default = true;
        description = "Enable or disable the data offloading service";
    };

    config = pkgs.lib.mkIf config.data_offload_service.enable {

        systemd.services.data-offload-service = {
            description = "Data Offload Service";
            wantedBy = [ "multi-user.target" ];
            after = [ "network.target" ];

            serviceConfig = {
                After = [ "network.target" ];
                ExecStart = "/usr/bin/python3 ${pkgs.data_offload_service}/bin/offload.py";
                Restart = "always";
            };
        };

    };

}