{ config, pkgs, lib, ... }:

{
  imports = [ <nixpkgs/nixos/modules/installer/scan/not-detected.nix> ];

  # ─── System ───────────────────────────────────────────────
  system.stateVersion = "24.11";
  networking.hostName = "delpa-box";
  time.timeZone = "America/New_York";
  i18n.defaultLocale = "en_US.UTF-8";

  # ─── Unfree ──────────────────────────────────────────────
  nixpkgs.config.allowUnfree = true;

  # ─── Boot ─────────────────────────────────────────────────
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  # ─── User ─────────────────────────────────────────────────
  users.users.you = {
    isNormalUser = true;
    extraGroups = [ "wheel" "audio" "input" "video" "networkmanager" ];
    shell = pkgs.bash;
  };

  # ─── Desktop (GNOME) ─────────────────────────────────────
  services.xserver.enable = true;
  services.xserver.displayManager.gdm.enable = true;
  services.xserver.desktopManager.gnome.enable = true;

  # ─── Audio (PipeWire) ────────────────────────────────────
  services.pipewire = {
    enable = true;
    pulse.enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    wireplumber.enable = true;
  };
  security.rtkit.enable = true;

  # ─── Network ─────────────────────────────────────────────
  networking.networkmanager.enable = true;

  # ─── Sound ───────────────────────────────────────────────
  hardware.pulseaudio.enable = false;

  # ─── System Packages ─────────────────────────────────────
  environment.systemPackages = with pkgs; [
    # Core
    firefox
    git
    wget
    curl
    vim
    gnome-terminal

    # Python (full env with deps for jarvis)
    (python3.withPackages (ps: with ps; [
      vosk
      pynput
      pyautogui
      python-xlib
      numpy
      onnxruntime
      protobuf
      flatbuffers
      packaging
      pathvalidate
      pillow
      scipy
      scikit-learn
      requests
      click
      jinja2
      pyyaml
      tqdm
      cffi
      certifi
      charset-normalizer
      urllib3
      idna
      six
      pyparsing
      setuptools
      joblib
      threadpoolctl
      python-dateutil
      pytz
      rich
      typer
      shellingham
      markdown-it-py
      mdurl
      pygments
    ]))

    # TTS engine
    piper-tts

    # Audio capture
    alsa-utils
    portaudio

    # GUI automation helpers
    xdotool

    # Dev
    nodejs
  ];

  # ─── JARVIS Service ──────────────────────────────────────
  systemd.services.jarvis = {
    description = "JARVIS Voice Assistant — Right Shift PTT";
    after = [ "graphical-session.target" ];
    wantedBy = [ "default.target" ];
    serviceConfig = {
      ExecStart = "${pkgs.python3.withPackages (ps: with ps; [
        vosk pynput pyautogui python-xlib numpy onnxruntime protobuf flatbuffers packaging pathvalidate pillow requests certifi charset-normalizer urllib3 idna six cffi
      ])}/bin/python -u /home/you/jarvis/main_final.py";
      Restart = "on-failure";
      RestartSec = 5;
      User = "you";
      Environment = "DISPLAY=:0";
    };
  };

  # ─── Fonts ───────────────────────────────────────────────
  fonts.packages = with pkgs; [
    noto-fonts
    noto-fonts-emoji
    liberation_ttf
  ];

  # ─── AdGuard Home (network-level adblocker) ────────────
  services.adguardhome = {
    enable = true;
    mutableSettings = true;
  };

  # ─── Security / Misc ────────────────────────────────────
  services.openssh.enable = true;
  programs.mtr.enable = true;
  programs.gnupg.agent = {
    enable = true;
    enableSSHSupport = true;
  };
}
