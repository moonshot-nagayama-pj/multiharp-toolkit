use arrow::array::{UInt16Array, UInt64Array};
use arrow::datatypes::{DataType, Field, Schema};
use arrow::record_batch::RecordBatch;
use chrono::Utc;
use parquet::arrow::ArrowWriter;
use std::fs::File;
use std::path::Path;
use std::sync::{mpsc, Arc};

// Write a series of Parquet files to disk containing the data from the
// input queue.
//
// For write efficiency and ease in handling large volumes of data, we
// batch writes to Parquet files in chunks of about 200 MiB (as
// recommended in this discussion
// https://github.com/apache/arrow/issues/13142, and then rotate to a new
// file approximately every 2 GiB. Rows are assumed to contain about 80
// bits of data each; ignoring metadata overhead and compression, this
// means that a 2 GiB file can hold approximately 214,700,000 rows. For
// simplicity, we set the default size limit for each file to 200,000,000
// rows, and default chunk size to 20,000,000.
//
// The GitHub issue above discusses using ``sys.getsizeof()`` to
// determine the number of bytes used by a data structure. This may work
// for some object types, but, generally speaking, ``getsizeof()`` will
// only report the amount of memory used by a container object, not the
// objects contained within that object. For this reason, we rely on row
// counts rather than actual byte counts.

pub struct T2RecordParquetWriter {
    // The maximum number of total rows (records) that should be
    // collected before writing to disk.
    max_chunk_rows: usize,
    // The maximum number of total rows (records) that should be
    // allowed per file.
    max_file_rows: usize,
}

impl T2RecordParquetWriter {
    pub fn new() -> T2RecordParquetWriter {
        T2RecordParquetWriter {
            max_chunk_rows: 20_000_000,
            max_file_rows: 200_000_000,
        }
    }

    pub fn write(
        &self,
        rx_channel: mpsc::Receiver<Vec<(u16, u64)>>,
        output_dir: &Path,
        name: &str,
    ) -> Result<(), ()> {
        if !output_dir.is_dir() {
            return Err(());
        }
        let fields = vec![
            Field::new("channel", DataType::UInt16, false),
            Field::new("time_tag", DataType::UInt64, false),
        ];
        let schema: Arc<Schema> = Schema::new(fields).into();

        let max_chunk_count = self.max_file_rows / self.max_chunk_rows;
        let file_timestamp = Utc::now().format("%Y%m%dT%H%M%SZ");

        let mut total_files = 1;
        let initial_file = File::create_new(output_dir.join(format!(
            "{}_{}_{:0>4}.parquet",
            file_timestamp, name, total_files
        )))
        .unwrap();
        let mut arrow_writer = ArrowWriter::try_new(initial_file, schema.clone(), None).unwrap();
        let mut channel_array_builder = UInt16Array::builder(self.max_chunk_rows);
        let mut time_tag_array_builder = UInt64Array::builder(self.max_chunk_rows);
        let mut array_length = 0;
        let mut chunk_count = 0;
        for rx_batch in rx_channel {
            for event in rx_batch {
                array_length += 1;
                channel_array_builder.append_value(event.0);
                time_tag_array_builder.append_value(event.1);
            }

            if array_length >= self.max_chunk_rows {
                // write current batch into current file
                let batch = RecordBatch::try_new(
                    schema.clone(),
                    vec![
                        Arc::new(channel_array_builder.finish()),
                        Arc::new(time_tag_array_builder.finish()),
                    ],
                )
                .unwrap();
                arrow_writer.write(&batch).unwrap();
                array_length = 0;
                chunk_count += 1;
            }

            if chunk_count > max_chunk_count {
                // close and replace file
                arrow_writer.close().unwrap();
                chunk_count = 0;
                total_files += 1;

                let new_file = File::create_new(output_dir.join(format!(
                    "{}_{}_{:0>4}.parquet",
                    file_timestamp, name, total_files
                )))
                .unwrap();
                arrow_writer = ArrowWriter::try_new(new_file, schema.clone(), None).unwrap();
            }
        }

        // write any remaining data
        if array_length > 0 {
            let batch = RecordBatch::try_new(
                schema.clone(),
                vec![
                    Arc::new(channel_array_builder.finish()),
                    Arc::new(time_tag_array_builder.finish()),
                ],
            )
            .unwrap();
            arrow_writer.write(&batch).unwrap();
        }
        arrow_writer.close().unwrap();

        Ok(())
    }
}

impl Default for T2RecordParquetWriter {
    fn default() -> Self {
        Self::new()
    }
}
