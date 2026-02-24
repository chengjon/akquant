use crate::engine::Engine;
use crate::pipeline::processor::{Processor, ProcessorResult};
use pyo3::prelude::*;

pub struct PipelineRunner {
    processors: Vec<Box<dyn Processor>>,
}

impl Default for PipelineRunner {
    fn default() -> Self {
        Self::new()
    }
}

impl PipelineRunner {
    pub fn new() -> Self {
        Self {
            processors: Vec::new(),
        }
    }

    pub fn add_processor(&mut self, processor: Box<dyn Processor>) {
        self.processors.push(processor);
    }

    pub fn run(&mut self, engine: &mut Engine, py: Python<'_>, strategy: &Bound<'_, PyAny>) -> PyResult<()> {
        'main_loop: loop {
            for processor in &mut self.processors {
                match processor.process(engine, py, strategy)? {
                    ProcessorResult::Next => {},
                    ProcessorResult::Loop => continue 'main_loop,
                    ProcessorResult::Break => break 'main_loop,
                }
            }
        }
        Ok(())
    }
}
