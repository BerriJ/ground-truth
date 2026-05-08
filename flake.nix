{
  description = "Python development environment with CUDA support";
  # See also "https://nixos.org/manual/nixpkgs/"

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux"; # Adjust if necessary
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        config.cudaSupport = true;
      };
      pypkgs = pkgs.python3Packages;
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        name = "Python";
        venvDir = "./.venv";

        buildInputs = [

          # Stuff needed for technical reasons
          pypkgs.python
          pypkgs.ipykernel
          pypkgs.jupyterlab
          pypkgs.pyzmq # Adding pyzmq explicitly
          pypkgs.pip
          pypkgs.notebook
          pypkgs.jupyter
          pypkgs.jupyter-client
          pypkgs.venvShellHook

          # CUDA
          pkgs.cudaPackages.cudatoolkit
          pkgs.cudaPackages.cudnn
          pkgs.cudaPackages.cuda_cudart
        ];

        env = {
          NIX_LD = pkgs.lib.fileContents "${pkgs.stdenv.cc}/nix-support/dynamic-linker";

          LD_LIBRARY_PATH =
            pkgs.lib.makeLibraryPath (
              with pkgs;
              [
                libz
                glib
                zlib
                libGL
                stdenv.cc.cc
                stdenv.cc.cc.lib
                ncurses5
              ]
            )
            + ":/run/opengl-driver/lib";

          EXTRA_CCFLAGS = "-I/usr/include";
          CUDA_PATH = pkgs.cudaPackages.cudatoolkit;
        };

        # Run this command only after creating the virtual environment
        postVenvCreation = ''
          unset SOURCE_DATE_EPOCH
          pip install -r requirements.txt
        '';

        # Now we can execute any commands within the virtual environment.
        # This is optional and can be left out to run pip manually.
        postShellHook = ''
          # Allow pip to install wheels
          unset SOURCE_DATE_EPOCH
        '';
      };
    };
}
