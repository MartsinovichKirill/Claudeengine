using System;
using System.Linq;
using System.Reflection;
using System.Web.Script.Serialization;
namespace CloudEngine {
    public abstract class CloudBehaviour {
        public double X, Y, VelocityX, VelocityY, Rotation, ScaleX=1, ScaleY=1;
        public bool OnFloor;
        public string Name;
        public virtual void Ready() {}
        public virtual void Process(double delta) {}
        public virtual void PhysicsProcess(double delta) {}
        public virtual void Exit() {}
    }
    public static class ScriptHost {
        public static void Main() {
            var serializer = new JavaScriptSerializer();
            var protocol = Console.Out;
            Console.SetOut(Console.Error);
            var type = Assembly.GetExecutingAssembly().GetTypes().First(t => !t.IsAbstract && typeof(CloudBehaviour).IsAssignableFrom(t));
            var script = (CloudBehaviour)Activator.CreateInstance(type);
            string line;
            while ((line = Console.ReadLine()) != null) {
                try {
                    var state = serializer.Deserialize<System.Collections.Generic.Dictionary<string,object>>(line);
                    foreach (var field in typeof(CloudBehaviour).GetFields()) {
                        if (state.ContainsKey(field.Name)) field.SetValue(script, Convert.ChangeType(state[field.Name], field.FieldType));
                    }
                    string method = (string)state["event"];
                    double delta = Convert.ToDouble(state["delta"]);
                    if (method == "ready") script.Ready();
                    else if (method == "process") script.Process(delta);
                    else if (method == "physics") script.PhysicsProcess(delta);
                    else if (method == "exit") script.Exit();
                    protocol.WriteLine(serializer.Serialize(new {script.X, script.Y, script.VelocityX, script.VelocityY, script.Rotation, script.ScaleX, script.ScaleY}));
                    protocol.Flush();
                    if (method == "exit") break;
                } catch (Exception ex) { protocol.WriteLine(serializer.Serialize(new {error=ex.Message})); protocol.Flush(); }
            }
        }
    }
}
