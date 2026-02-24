use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::cmp::Ordering;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Timer {
    #[pyo3(get, set)]
    pub timestamp: i64,
    #[pyo3(get, set)]
    pub payload: String,
}

impl Ord for Timer {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse order for Min-Heap behavior in BinaryHeap
        other.timestamp.cmp(&self.timestamp)
    }
}

impl PartialOrd for Timer {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
