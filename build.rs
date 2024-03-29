use std::env;
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-changed=wrapper.h");
    let os = env::consts::OS;
    let arch = env::consts::ARCH;
    if arch != "x86_64" || (os != "linux" && os != "windows") {
        return;
    }
    let mut lib_dir = String::from("");
    if os == "linux" {
        // this requires the MHLib_v3.x.x_64bit directory to be in the same directory as the Cargo.toml file
        let manifest_dir = env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR not set");

        // if the MHLIB_PATH environment variable is provided, use it
        let lib_dir_path = env::var("MHLIB_PATH").map_or(
            PathBuf::from(manifest_dir).join("MHLib_v3.1.0.0_64bit/library"),
            PathBuf::from,
        );
        assert!(
            lib_dir_path.exists(),
            "Library directory does not exist: {}",
            lib_dir_path.display()
        );
        lib_dir = lib_dir_path.to_string_lossy().into_owned();
        println!("cargo:rustc-link-search={}", lib_dir);
        println!("cargo:rustc-link-lib=dylib=mhlib");
        println!("cargo:rustc-link-arg=-Wl,-rpath={}", lib_dir);
    }

    if os == "windows" {
        lib_dir = String::from("C:\\Program Files\\PicoQuant\\MultiHarp-MHLibv31");
        println!("cargo:rustc-link-search=native={}", lib_dir);
        println!("cargo:rustc-link-lib=dylib=mhlib64");
    }

    // The bindgen::Builder is the main entry point
    // to bindgen, and lets you build up options for
    // the resulting bindings.
    let bindings = bindgen::Builder::default()
        // The input header we would like to generate
        // bindings for.
        .header("wrapper.h")
        .clang_arg(format!("-I{}", lib_dir))
        // Tell cargo to invalidate the built crate whenever any of the
        // included header files changed.
        .parse_callbacks(Box::new(bindgen::CargoCallbacks::new()))
        // Finish the builder and generate the bindings.
        .generate()
        // Unwrap the Result and panic on failure.
        .expect("Unable to generate bindings");

    // Write the bindings to the $OUT_DIR/bindings.rs file.
    let out_path = PathBuf::from(env::var("OUT_DIR").unwrap());
    bindings
        .write_to_file(out_path.join("bindings.rs"))
        .expect("Couldn't write bindings!");
}
