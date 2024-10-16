{ config, lib, pkgs, ... }:

{
    options.data-offload-service.enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable or disable the data offloading service";
    };

    config = lib.mkIf config.drivebrain-service.enable {

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