// no imports needed — this component is pure props + rendering

interface CartStatsProps {
  data: {
    soc: number;
    v_out: number;
    v_cells: number[];
    current: number;
    temp_BMS: number;
    temp_cell1: number;
    temp_cell2: number;
    temp_cell3: number;
    speed_MPH: number;
  };
}

type DataType = "SOC" | "VOLTAGE" | "CURRENT" | "POWER";

const BATTERY_SERIAL = "EB2605LC1423";
const BATTERY_CAPACITY_KWH = 5.3;
const BATTERY_MODEL = "51V 105Ah LiFePO4 Heated";

//Helper function to determine SOC bar color based on percentage (Green >50%, Yellow 20-50%, Red <20%)
const getSOCColor = (soc: number) => {
  if (soc > 50) {
    const ratio = (soc - 50) / 50;
    const r = Math.round(239 - (239 - 34) * ratio);
    const g = Math.round(68 - (68 - 197) * ratio);
    const b = Math.round(68 - 68 * ratio);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    const ratio = soc / 50;
    const r = Math.round(239);
    const g = Math.round(168 * ratio);
    const b = Math.round(0);
    return `rgb(${r}, ${g}, ${b})`;
  }
};

export default function BatteryStats({ data }: CartStatsProps) {
  const kWhRemaining = ((data.soc / 100) * BATTERY_CAPACITY_KWH).toFixed(1);
  const powerDraw = data.current * data.v_out;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "16px",
        margin: "20px",
        backgroundColor: "#0d0d0d",
        borderRadius: "40px",
        fontFamily: "sans-serif",
        fontWeight: "bold",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          padding: "10px",
          color: "#22c55e",
          backgroundColor: "#0f3d1f",
          borderRadius: "20px",
          fontSize: "20px",
          fontFamily: "sans-serif",
          justifyContent: "center",
          width: "fit-content",
          alignItems: "center",
        }}
      >
        {/*Battery Name & Status*/}
        <div
          style={{
            width: "10px",
            height: "10px",
            borderRadius: "50%",
            backgroundColor: "#22c55e",
            marginRight: "8px",
          }}
        />
        ECO BATTERY GEN 3
      </div>

      {/*Battery Model & Serial*/}
      <span
        style={{
          marginTop: "14px",
          fontSize: "16px",
          color: "#404040",
          marginLeft: "4px",
        }}
      >
        {BATTERY_MODEL}
      </span>
      <span
        style={{
          marginTop: "2px",
          marginBottom: "10px",
          marginLeft: "4px",
          color: "#323230",
          fontSize: "14px",
          fontFamily: "sans-serif",
        }}
      >
        S/N: {BATTERY_SERIAL}
      </span>

      {/*Battery Specs*/}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          justifyContent: "space-between",
          gap: "10px",
          alignItems: "center",
        }}
      >
        <BatterySpecPill value="51V" label="NOMINAL" />
        <BatterySpecPill value="105Ah" label="CAPACITY" />
        <BatterySpecPill value={`${BATTERY_CAPACITY_KWH}kWh`} label="TOTAL" />
      </div>

      <DividerLine />

      {/*Live Battery Data*/}
      <div>
        <LiveBatteryDataHeader title="STATE OF CHARGE" />
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "flex-end",
            marginTop: "0px",
          }}
        >
          <FormatData data={data.soc} type="SOC" />
          <span
            style={{
              color: getSOCColor(data.soc),
              fontSize: "16px",
              margin: 0,
              paddingBottom: "10px",
              marginLeft: "auto",
              marginRight: "5px",
            }}
          >
            {kWhRemaining} kWh Remaining
          </span>
        </div>
        <div
          style={{
            width: "100%",
            height: "8px",
            backgroundColor: "#171717",

            borderRadius: "8px",
          }}
        >
          <div
            style={{
              width: `${data.soc}%`,
              height: "100%",
              backgroundColor: getSOCColor(data.soc),
              borderRadius: "8px",
            }}
          ></div>
        </div>
        <DividerLine />
        <LiveBatteryDataHeader title="VOLTAGE" />
        <FormatData data={data.v_out} type="VOLTAGE" />
        <LiveBatteryDataHeader title="CURRENT" />
        <FormatData data={data.current} type="CURRENT" />
        <DividerLine />
        <LiveBatteryDataHeader title="POWER DRAW" />
        <FormatData data={powerDraw} type="POWER" />
        <DividerLine />
        <FormatTemperature
          temp1={data.temp_cell1}
          temp2={data.temp_cell2}
          temp3={data.temp_cell3}
        />
      </div>
    </div>
  );
}

//Helper component for battery spec pills (Nominal Voltage, Capacity, Total Energy)
function BatterySpecPill({ value, label }: { value: string; label: string }) {
  return (
    <div
      style={{
        padding: "10px",
        backgroundColor: "#141414",
        borderRadius: "8px",
        justifyContent: "center",
        alignItems: "center",
        display: "flex",
        flexDirection: "column",
        width: "120px",
      }}
    >
      <span
        style={{
          color: "#666565",
        }}
      >
        {value}
      </span>
      <span
        style={{
          color: "#404040",
        }}
      >
        {label}
      </span>
    </div>
  );
}

//Helper component for divider lines between sections
function DividerLine() {
  return (
    <div
      style={{
        borderTop: "2px solid #171717",
        margin: "10px 5px",
      }}
    ></div>
  );
}

//Helper component for live data section headers (SOC, Voltage, Current, Power)
function LiveBatteryDataHeader({ title }: { title: string }) {
  return (
    <span
      style={{
        color: "#323230",
        fontSize: "20px",
      }}
    >
      {title}
    </span>
  );
}

//Helper components for formatting live battery data
function FormatData({ data, type }: { data: number; type: DataType }) {
  let mainValue;
  let minorValue;
  //Formats data based on type (SOC, Voltage, Current, Power)
  if (type === "SOC") {
    mainValue = data;
    minorValue = "%";
  } else if (type === "VOLTAGE") {
    mainValue = Math.floor(data);
    let v_out_decimal = Math.round((data - mainValue) * 10);
    minorValue = `.${v_out_decimal} V`;
  } else if (type === "CURRENT") {
    mainValue = data;
    minorValue = "A";
  } else if (type === "POWER") {
    mainValue = data.toFixed(0);
    minorValue = "W";
  }
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "flex-end",
      }}
    >
      <span
        style={{
          color: "white",
          fontSize: "60px",
        }}
      >
        {mainValue}
      </span>
      <span
        style={{
          color: "#323230",
          fontSize: "25px",
          marginBottom: "6px",
        }}
      >
        {minorValue}
      </span>
    </div>
  );
}

//Helper function to calculate and Format Avg Temperature of cells
function FormatTemperature({
  temp1,
  temp2,
  temp3,
}: {
  temp1: number;
  temp2: number;
  temp3: number;
}) {
  const avgTemp = (temp1 + temp2 + temp3) / 3;
  // Convert to Fahrenheit
  const avgTempF = avgTemp * (9 / 5) + 32;

  let tempColor;
  if (avgTempF < 32 || avgTempF > 131)
    tempColor = "#ef4444"; // temp no good
  else if (avgTempF > 113)
    tempColor = "#f59e0b"; // temp warning
  else tempColor = "#22c55e"; // temp good

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        padding: "1px",
      }}
    >
      <div
        style={{
          width: "10px",
          height: "10px",
          borderRadius: "50%",
          backgroundColor: tempColor,
          marginRight: "8px",
          marginTop: "5px",
        }}
      />
      <span
        style={{
          color: "#323230",
          fontSize: "20px",
          margin: 0,
          paddingBottom: "10px",
        }}
      >
        Avg Cell Temp
      </span>
      <span
        style={{
          color: "white",
          fontSize: "20px",
          marginLeft: "auto",
          marginRight: "5px",
        }}
      >
        {avgTempF.toFixed(1)} °F
      </span>
    </div>
  );
}
