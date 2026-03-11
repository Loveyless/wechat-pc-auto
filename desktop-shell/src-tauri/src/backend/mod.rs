mod bootstrap;
mod win32;

pub use bootstrap::{
    bootstrap_backend, get_backend_connection_info, log_single_instance_event, ManagedBackendState,
};
