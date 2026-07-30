//fft processor file
// called from the processor thread, receives frame of samples of amplitudes
// package up the samples from the buffer into a full window, then send the window
// fft algorithm

// fft algo takes in list of samples and processes them and returns the dominant frequencies



use rustfft::{num_complex::Complex32, FftPlanner};

pub struct FftProcessor{
    window_size : usize,
    sample_rate : f32,
    buff        : Vec<f32>,
    planner     : FftPlanner<f32>,
}



impl FftProcessor{
    pub fn new(sample_rate: f32, window_size: usize) -> Self{
        Self{
            window_size,
            sample_rate,
            buff: Vec::with_capacity(window_size),
            planner: FftPlanner::new(),
        }
    }

    //from the samples collected, populate buffer and send to fft planner when full
    //when fft returns magnitudes of the frequencies, use it to find the frequency with the highest
    // energy which will correspond to the pitch
    pub fn collect_and_process(&mut self, samples: &[f32]) -> Option<f32> {
        self.buff.extend_from_slice(samples);

        //buffer is not yet full
        if self.buff.len()<self.window_size{
            return None;
        }else{
            //create spectrum of complex numbers taken form the smaples of real nums
            let mut spectrum: Vec<Complex32> = self.buff[..self.window_size].iter().map(|&s| Complex32::new(s, 0.0)).collect();
            self.buff.drain(..self.window_size);
            let fft = self.planner.plan_fft_forward(self.window_size);
            fft.process(&mut spectrum);


            //get freq with max energy
            let (bin, _mag) = spectrum[..self.window_size/2].iter().enumerate()
                        .max_by(|(_, a), (_,b)| a.norm().partial_cmp(&b.norm()).unwrap())?;


            // the index of the bin containing the freq map
            let bin = bin+1;
            Some((bin as f32)*self.sample_rate/(self.window_size as f32))
        }
    }
}