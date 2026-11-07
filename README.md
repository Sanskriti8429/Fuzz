# Fuzz

**Catch the spark before it becomes a fire.**

Fuzz is a low-cost, multi-sensor early-warning device for electrical faults in homes. It installs at the distribution board and watches a branch circuit through independent sensors. It flags a developing fault early, cuts the supply if it escalates, and uses machine learning to estimate which appliance is likely at risk and roughly how far along the wiring the problem is.

> **Project type:** simulation-based capstone. The schematic is complete in KiCad. Circuit values are being confirmed by SPICE simulation, and the machine-learning models are trained on public datasets passed through simulated front-end and cable models. No hardware has been built or measured. See [Limitations](#limitations).

---

## Why this project

Most electrical fires start small: a loose terminal that arcs, insulation that slowly leaks, a joint that heats up. Standard MCBs and RCDs look at one signal and act only once the fault is already serious. Fuzz targets the gap between "normal" and "tripped", and tells the homeowner what is causing the threat.

## What it senses

Four warning channels and one supply-monitoring channel feed a single ESP32:

- **RF arc:** radio noise from sparking at loose joints. Loop antenna, LC tank, envelope detector.
- **Leakage current:** insulation breakdown. Current transformer (ZMCT103C), amplifier, rectifier.
- **di/dt:** very fast current rise, the signature of a short circuit. Coil, integrator, comparator.
- **Temperature:** hot, loose connections. NTC thermistor divider.
- **Mains voltage (supply monitoring):** over- and under-voltage and frequency. ZMPT101B voltage sensing module.

## Detection logic

Two tiers, evaluated on the ESP32:

- **WARNING (predictive):** two or more channels trend upward together over a rolling window. The user is notified and nothing is cut.
- **TRIP (protective):** a hard limit is crossed, or the di/dt comparator fires. The relay module opens the supply immediately, without depending on Wi-Fi or the server.

Thresholds are derived in the calculations report in `docs/`.

## Machine learning

The AI is what turns "something is wrong" into "something is wrong, probably here". Planned outputs:

- **Fault state:** normal, warning or trip.
- **Appliances at risk:** several appliances can run on one branch, so this is a multi-label problem.
- **Probable distance:** estimated distance in metres from the board along the wiring, reported with a confidence range (for example "about 10 m, likely 8 to 12 m").

How the training data is built:

1. Real appliance and arc current signatures come from public datasets (see [Datasets](#datasets)).
2. Multi-appliance cases are made by adding single-appliance currents together (Kirchhoff's current law), as in the NILM literature.
3. Those signals are passed through a simulated model of Fuzz's own sensing circuits and a cable model of 1 to 20 m. This produces the features Fuzz's ESP32 would actually see, together with distance labels.
4. Models are trained on those features and tested across datasets.

Models to compare:

- **Tree-based baselines:** Random Forest and XGBoost.
- **Deep models:** a 1D CNN, a ROCKET-type model, and a CNN-Transformer.
- **Multi-task model:** one shared model that outputs fault state, appliances and distance, compared against separate single-task models.

Also planned: a channel ablation (retrain with each sensor removed to show what each one contributes), SHAP explanations for each alert, and alert thresholds that treat false alarms as more costly than missed warnings.

The four-channel fusion itself is rule-based, because no public dataset contains all the sensor signals together.

## System architecture

*To be added.*

## Operator dashboard and client app

Planned, built in plain HTML and JavaScript:

- **Operator dashboard:** live status of every unit, the sensor readings over time, model outputs with confidence, alert history and settings.
- **Client mobile view:** a simple risk indicator, a plain-language message such as "arc activity, likely microwave, about 10 m away (8 to 12 m)", notifications and advice.

Until hardware exists, a simulator script plays the ESP32's role and sends scenarios (normal use, an arc at a given distance, rising leakage, overheating) to the backend.

## Repository structure

```
hardware/
  kicad/          Full-system schematic (KiCad), exported PDF, BOM
  simulation/     SPICE simulations of the analog stages
firmware/         ESP32 fusion and trip logic
ml/
  data/           Datasets (downloaded locally, not committed)
  *.py            Exploration, data generation, training, evaluation
backend/          Inference server (planned)
dashboard/        Operator dashboard and client view (planned)
demo/             Demo video scripts
docs/             Calculations report, schematic PDF
```

## Status

- [x] Sensing strategy and system design
- [x] Full-system schematic in KiCad (ERC run, 0 violations)
- [x] Exported schematic PDF and BOM
- [ ] Analog stages simulated in SPICE and component values confirmed
- [ ] Cable and arc-source model for the distance data
- [ ] Datasets downloaded and explored
- [ ] Training-data generation pipeline
- [ ] Models trained, compared and evaluated across datasets
- [ ] ESP32 fusion logic
- [ ] Backend, ESP32 simulator, operator dashboard and client view
- [ ] Calculations report updated to match the schematic
- [ ] Demo video

## Datasets

Datasets are not stored in this repo. They are downloaded locally into `ml/data/`. Licences are to be confirmed before use.

- **Arc faults (main):** Ferracuti et al., 2025. Series arc current signatures from 13 load types, 230 V / 50 Hz, IEC 62606. [doi.org/10.5281/zenodo.15279701](https://doi.org/10.5281/zenodo.15279701)
- **Arc faults (cross-dataset test):** Series AC arc fault data from a 230 V / 50 Hz domestic network, University of Lorraine and Huaqiao University. [zenodo.org/record/3997337](https://zenodo.org/record/3997337)
- **Appliance identification (main):** PLAID, appliance voltage and current at 30 kHz, including aggregated recordings. Scientific Data, 2020, doi 10.1038/s41597-020-0389-7.
- **Appliance identification (validation):** COOLL, 42 appliances sampled at 100 kHz. arXiv 1611.05803.
- **Optional:** Texas Instruments `ac_arc_fault_log300`, for testing false alarms from masking loads such as dimmers and drills.

No public dataset contains distance, so distance labels come from the simulated cable model.

## Results

- **Fault state:** TBD
- **Appliance identification:** TBD
- **Distance estimation (mean absolute error in metres):** TBD

Numbers are filled in only after the evaluation scripts have been run.

## Limitations

- **Simulation only.** Nothing has been built or measured. Circuit values are confirmed by simulation, not on hardware.
- **Distance is simulated.** Distance labels come from a cable model, so accuracy is only as good as that model. Real wiring has junctions, branches and other loads. Distance is reported as a probable range, and field validation is future work.
- **Appliance guesses are probabilities.** With several appliances running, one can mask another. Results are reported with confidence and a confusion matrix.
- **Dataset domain gap.** Public datasets were recorded at the appliance, not through a long cable, and with different equipment from Fuzz's sensors.
- **Rule-based fusion.** Fusion thresholds come from calculation and simulation, not from field data.
- **Not a certified device.** This is an educational prototype and must not be used as a safety product.
