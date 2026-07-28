use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{InputCallbackInfo, StreamConfig};
use ringbuf::traits::{Consumer, Producer, Split};
use ringbuf::HeapRb;
use std::thread;
use std::time::Duration;

const RING_SIZE: usize = 8192;

// create threads for capturing audio and processing signals
pub fn run(){
    // configure ring buffer
    let ring_buffer = HeapRb::<f32>::new(RING_SIZE);
    let (p, c) = ring_buffer.split();

    //init threads on ring buffer parts
    let capture = thread::spawn(move || capture_thread(p));
    let process = thread::spawn(move || processer_thread(c));

    capture.join().unwrap();
    process.join().unwrap();
}


fn capture_thread(mut producer: impl Producer<Item = f32> + Send + 'static){
    let host = cpal::default_host();
    let device = host.default_input_device().expect("no input found");
    let stream_config: StreamConfig = device.default_input_config().expect("no default input config").into();

    let stream = device.build_input_stream(
        stream_config, 
        move |clip: &[f32], _: &InputCallbackInfo| { producer.push_slice(clip); },
        |err| eprintln!("istream err: {err}"),
        None,
    ).expect("failed to build input stream");

    stream.play().expect("input stream start fail");


    loop{
        thread::park();
    }
}


fn processer_thread(mut consumer: impl Consumer<Item = f32>){
    loop{
        let mut drained = 0;
        while let Some(sample) = consumer.try_pop(){
            let db = 20.0*sample.abs().max(1e-12).log10();

            println!("{sample:.4}, {db:.4}");
            drained+=1; 

        }

        if drained>0{
            println!("processed {drained} samples")
        }

        thread::sleep(Duration::from_millis(10));
    }
}