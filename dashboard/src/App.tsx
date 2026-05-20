import { useState, useEffect } from "react";
import Speedometer from "./Speedometer";

interface battery_data {
  soc: number;
  v_out: number;
  v_cells: number[];
  current: number;
  temp_BMS: number;
  temp_cell1: number;
  temp_cell2: number;
  temp_cell3: number;
  temp_cell4: number;
}
export default function App() {
  const [data, setData] = useState<battery_data>({
    soc: 0,
    v_out: 0,
    v_cells: Array(16).fill(0),
    current: 0,
    temp_BMS: 0,
    temp_cell1: 0,
    temp_cell2: 0,
    temp_cell3: 0,
    temp_cell4: 0,
  });

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8765");
    ws.onmessage = (event) => {
      const newData = JSON.parse(event.data);
      setData(newData);
    };
    return () => {
      ws.close();
    };
  }, []);

  return (
    <div>
      <h1>Battery Data</h1>
      <p>State of Charge: {data.soc}%</p>
      <p>Output Voltage: {data.v_out} V</p>
      <p>Cell Voltages: {data.v_cells.join(", ")} V</p>
      <p>Current: {data.current} A</p>
      <p>BMS Temperature: {data.temp_BMS} °C</p>
      <p>Cell 1 Temperature: {data.temp_cell1} °C</p>
      <p>Cell 2 Temperature: {data.temp_cell2} °C</p>
      <p>Cell 3 Temperature: {data.temp_cell3} °C</p>
      <p>Cell 4 Temperature: {data.temp_cell4} °C</p>
      <Speedometer />
    </div>
  );
}
