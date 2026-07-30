mod audio;
mod dsp;

use std::thread;

fn main() {
    let handle = thread::spawn(audio::run);

    handle.join().unwrap();

    //audio::run();
}
