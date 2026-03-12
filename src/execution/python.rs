use crate::event::Event;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::model::{Order, Trade};
use pyo3::IntoPyObjectExt;
use pyo3::prelude::*;

/// Python 自定义撮合器包装器
///
/// 将 Rust 的 ExecutionMatcher trait 转发给 Python 对象。
/// Python 对象需要实现 `match` 方法:
/// `def match(self, order: Order, event: Union[Bar, Tick], instrument: Instrument) -> Optional[Trade]: ...`
pub struct PyExecutionMatcher {
    inner: Py<PyAny>,
}

impl PyExecutionMatcher {
    pub fn new(obj: Py<PyAny>) -> Self {
        Self { inner: obj }
    }
}

impl ExecutionMatcher for PyExecutionMatcher {
    fn match_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event> {
        let event = ctx.event;
        let instrument = ctx.instrument;
        let bar_index = ctx.bar_index;

        Python::attach(|py| {
            // 1. Convert arguments to Python objects
            // Use clone() to create a copy for Python
            let py_order = order.clone().into_py_any(py).ok()?;

            let py_event = match event {
                Event::Bar(b) => b.clone().into_py_any(py).ok()?,
                Event::Tick(t) => t.clone().into_py_any(py).ok()?,
                _ => return None, // Only support matching on Bar/Tick
            };

            let py_instrument = instrument.clone().into_py_any(py).ok()?;

            // 2. Call Python `match` method
            // Signature: match(self, order, event, instrument) -> Optional[Trade]
            // Note: The Python method is expected to modify `order` in-place if needed,
            // and return a Trade if a trade occurred.
            let args = (py_order.clone_ref(py), py_event, py_instrument, bar_index);

            match self.inner.call_method1(py, "match", args) {
                Ok(result) => {
                    // 3. Check result
                    if result.is_none(py) {
                        return None;
                    }

                    // 4. If result is a Trade, extract it
                    if let Ok(trade) = result.extract::<Trade>(py) {
                        // 5. Sync back modified Order state from Python object
                        if let Ok(updated_order) = py_order.extract::<Order>(py) {
                            *order = updated_order;
                        } else {
                            // Log warning? Failed to extract updated order
                            // eprintln!("PyExecutionMatcher: Failed to extract updated Order from Python");
                        }

                        // 6. Return ExecutionReport
                        Some(Event::ExecutionReport(order.clone(), Some(trade)))
                    } else {
                        // eprintln!("PyExecutionMatcher: Python match method returned something that is not a Trade or None");
                        None
                    }
                }
                Err(e) => {
                    e.print_and_set_sys_last_vars(py);
                    None
                }
            }
        })
    }
}
