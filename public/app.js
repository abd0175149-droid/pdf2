const form = document.getElementById("ocrForm");
const progressBar = document.getElementById("progressBar");
const resultDiv = document.getElementById("result");
const previewText = document.getElementById("previewText");
const downloadLink = document.getElementById("downloadLink");

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const file = document.getElementById("fileInput").files[0];
  const apiKey = document.getElementById("apiKey").value.trim();

  if (!file) {
    alert("الرجاء اختيار ملف PDF أولاً!");
    return;
  }

  // إعادة تعيين الواجهة
  resultDiv.classList.add("hidden");
  progressBar.style.width = "0%";

  const formData = new FormData();
  formData.append("file", file);
  if (apiKey) formData.append("api_key", apiKey);

  try {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/ocr", true);

    // شريط التقدم أثناء الرفع
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        progressBar.style.width = percent + "%";
      }
    };

    xhr.onload = async () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        previewText.textContent = data.preview || "لم يتم العثور على نص.";
        downloadLink.href = data.download_url;
        resultDiv.classList.remove("hidden");
        progressBar.style.width = "100%";
      } else {
        alert("حدث خطأ أثناء التحليل: " + xhr.responseText);
      }
    };

    xhr.send(formData);
  } catch (err) {
    alert("حدث خطأ أثناء الاتصال بالخادم.");
    console.error(err);
  }
});
